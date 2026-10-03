"""Lee el código y escribe docs/INDICE.md: qué ficheros toca cada funcionalidad.

El problema que resuelve: para cambiar una pantalla hay que averiguar primero
dónde vive, y averiguarlo leyendo el repo cuesta más que el cambio. Los
documentos escritos a mano envejecían en silencio (`docs/05-frontend.md`
describe un Next.js que nunca existió), así que este índice se GENERA del
código, y se vuelve a generar cuando el código cambia:

    python backend/scripts/indice.py

La cadena que sigue, por cada ruta de la aplicación:

    ruta -> página -> función de services/api.ts -> ruta HTTP -> endpoint
         -> capa de aplicación -> motores de dominio -> tests

Nada de eso se escribe a mano: sale de las importaciones y de los decoradores.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parents[2]
FRONT = RAIZ / "frontend" / "src"
BACK = RAIZ / "backend" / "app"
TESTS = RAIZ / "backend" / "tests"


def leer(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def lineas(p: Path) -> int:
    return len(leer(p).splitlines()) if p.exists() else 0


# --------------------------------------------------------------- frontend

IMPORT = re.compile(
    r"import\s+(?:type\s+)?(\{[^}]*\}|[\w*]+(?:\s*,\s*\{[^}]*\})?)\s+from\s+['\"]([^'\"]+)['\"]",
    re.S,
)


def importaciones(texto: str) -> list[tuple[list[str], str]]:
    """[(nombres, módulo)] de cada import, con las llaves deshechas."""
    out = []
    for crudo, modulo in IMPORT.findall(texto):
        partes = re.sub(r"[{}]", ",", crudo).split(",")
        nombres = [n.strip().split(" as ")[0].strip() for n in partes]
        out.append(([n for n in nombres if n], modulo))
    return out


def rutas_de_app() -> list[tuple[str, str]]:
    """[(ruta, nombre del componente)] leídas de App.tsx, en su orden."""
    texto = leer(FRONT / "App.tsx")
    fichas = re.findall(r'path="([^"]+)"|<([A-Z][A-Za-z]+)\s*/>', texto)
    salida: list[tuple[str, str]] = []
    pendiente: str | None = None
    for ruta, comp in fichas:
        if ruta:
            pendiente = ruta
        elif comp and pendiente is not None and comp != "Navigate":
            salida.append((pendiente, comp))
            pendiente = None
    return salida


def fichero_de_componente() -> dict[str, Path]:
    """Nombre del componente -> fichero, según los imports de App.tsx."""
    texto = leer(FRONT / "App.tsx")
    mapa: dict[str, Path] = {}
    for nombres, modulo in importaciones(texto):
        if modulo.startswith("."):
            for n in nombres:
                mapa[n] = (FRONT / modulo.lstrip("./")).with_suffix(".tsx")
    # Las diferidas no son un import: const X = diferida(() => import(".."), "X")
    patron = r'const\s+(\w+)\s*=\s*diferida\(\s*\(\)\s*=>\s*import\("([^"]+)"\)'
    for var, modulo in re.findall(patron, texto, re.S):
        mapa[var] = (FRONT / modulo.lstrip("./")).with_suffix(".tsx")
    return mapa


def ficheros_de_api() -> list[Path]:
    """Dónde vive el cliente: `services/api/*.ts`, o el `api.ts` de antes."""
    carpeta = FRONT / "services" / "api"
    if carpeta.is_dir():
        return sorted(p for p in carpeta.glob("*.ts") if p.name != "index.ts")
    suelto = FRONT / "services" / "api.ts"
    return [suelto] if suelto.exists() else []


def miembro_a_fichero() -> dict[str, str]:
    """Miembro de `api` -> fichero de `services/api/` donde se escribe.

    Para no tener que buscarlo: añadir una llamada va al fichero de su
    funcionalidad, nunca a la fachada.
    """
    mapa: dict[str, str] = {}
    for fichero in ficheros_de_api():
        texto = leer(fichero)
        for obj in re.finditer(r"^export const api\w* = \{\n(.*?)^\};", texto, re.S | re.M):
            for m in re.finditer(r"^  (\w+):", obj.group(1), re.M):
                mapa[m.group(1)] = fichero.relative_to(RAIZ).as_posix()
    return mapa


def api_a_rutas() -> dict[str, list[str]]:
    """Miembro de `api` -> rutas HTTP que pide.

    Los miembros viven repartidos en objetos `apiJuveniles`, `apiLiga`... uno
    por funcionalidad, y la fachada los junta. Hay que trocear cada objeto por
    miembro: no vale con mirar qué fichero lo importa, porque una página que
    importa `api` importaría los 65.
    """
    mapa: dict[str, list[str]] = {}
    for fichero in ficheros_de_api():
        texto = leer(fichero)
        for obj in re.finditer(r"^export const api\w* = \{\n(.*?)^\};", texto, re.S | re.M):
            cuerpo = obj.group(1)
            cortes = [(m.start(), m.group(1)) for m in re.finditer(r"^  (\w+):", cuerpo, re.M)]
            for i, (inicio, nombre) in enumerate(cortes):
                fin = cortes[i + 1][0] if i + 1 < len(cortes) else len(cuerpo)
                bloque = cuerpo[inicio:fin]
                # El bloque entero, no línea a línea: hay miembros que arman la
                # consulta primero y dejan el `request` cuatro líneas más abajo.
                rutas = re.findall(
                    r"request<.*?>\(\s*[`'\"]([^`'\"$]*(?:\$\{[^}]*\}[^`'\"$]*)*)", bloque, re.S
                )
                rutas += re.findall(r"fetch\(\s*`\$\{BASE\}([^`]+)`", bloque, re.S)
                if rutas:
                    mapa[nombre] = rutas
    return mapa


def resolver(p: Path) -> Path | None:
    """El fichero real de un import relativo, con su extensión puesta."""
    for cand in (
        p.with_suffix(".tsx"),
        p.with_suffix(".ts"),
        p / "index.tsx",
        p / "index.ts",
    ):
        if cand.exists():
            return cand
    return None


SEGMENTOS: dict[Path, dict[str, str]] = {}


def segmentos(p: Path) -> dict[str, str]:
    """Símbolo exportado -> su cuerpo, troceando el fichero por los `export`.

    Hace falta porque los hooks viven todos juntos en `useTeam.ts`: si una
    página importa `useClub`, contarle todo lo que pide el fichero entero la
    ataría a media aplicación y el índice no serviría para nada.
    """
    if p in SEGMENTOS:
        return SEGMENTOS[p]
    texto = leer(p)
    cortes = [
        (m.start(), m.group(1))
        for m in re.finditer(
            r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class|type|interface)\s+(\w+)",
            texto,
            re.M,
        )
    ]
    out: dict[str, str] = {}
    for i, (inicio, nombre) in enumerate(cortes):
        fin = cortes[i + 1][0] if i + 1 < len(cortes) else len(texto)
        out[nombre] = texto[inicio:fin]
    SEGMENTOS[p] = out
    return out


REEXPORTES: dict[Path, dict[str, str]] = {}


def reexportes(p: Path) -> dict[str, str]:
    """Símbolo -> módulo del que lo reexporta una fachada.

    `services/api/index.ts` y `hooks/useTeam/index.ts` no declaran nada: dicen
    `export { useClub } from "./club"`. Sin esto el recorrido se para en la
    fachada y la pantalla parece no pedir datos a nadie.
    """
    if p in REEXPORTES:
        return REEXPORTES[p]
    mapa: dict[str, str] = {}
    patron = r"export\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['\"]([^'\"]+)['\"]"
    for m in re.finditer(patron, leer(p), re.S):
        for nombre in m.group(1).split(","):
            limpio = nombre.strip().split(" as ")[-1].strip()
            if limpio:
                mapa[limpio] = m.group(2)
    REEXPORTES[p] = mapa
    return mapa


def alcance(f: Path) -> tuple[set[str], set[Path]]:
    """Qué miembros de `api` acaba pidiendo una página, y por qué ficheros.

    Recorre (fichero, símbolo) en vez de (fichero): de `useTeam.ts` sólo
    cuenta el hook que se importó, no sus 60 vecinos.
    """
    api_usada: set[str] = set()
    tocados: set[Path] = set()
    pendiente: list[tuple[Path, str | None]] = [(f, None)]
    vistos: set[tuple[Path, str | None]] = set()

    while pendiente:
        fichero, simbolo = pendiente.pop()
        if (fichero, simbolo) in vistos or not fichero.exists():
            continue
        vistos.add((fichero, simbolo))
        tocados.add(fichero)
        segs = segmentos(fichero)
        cuerpo = leer(fichero) if simbolo is None else segs.get(simbolo, "")
        if simbolo is not None and not cuerpo:
            # No lo declara: puede que lo reexporte, y entonces hay que seguir.
            vecino = reexportes(fichero).get(simbolo)
            if vecino and vecino.startswith("."):
                destino = resolver((fichero.parent / vecino).resolve())
                if destino:
                    pendiente.append((destino, simbolo))
            continue
        api_usada |= set(re.findall(r"\bapi\.(\w+)", cuerpo))
        # Las importaciones son del fichero entero; sólo se siguen los nombres
        # que este cuerpo menciona de verdad.
        for nombres, modulo in importaciones(leer(fichero)):
            if not modulo.startswith(".") or modulo.endswith("services/api"):
                continue
            destino = resolver((fichero.parent / modulo).resolve())
            if not destino:
                continue
            for n in nombres:
                if re.search(rf"\b{re.escape(n)}\b", cuerpo):
                    pendiente.append((destino, n))
    return api_usada, tocados


def normalizar(ruta: str) -> str:
    """De `/teams/${teamId}/arena${qs ? ... }` a `/teams/:x/arena`.

    Un hueco es un parámetro (`${teamId}` -> `:x`) salvo que lleve dentro un
    `?`, que entonces es el armador de la consulta y no es parte de la ruta.
    Las llaves se cuentan a mano porque esos armadores anidan.
    """
    salida: list[str] = []
    i = 0
    while i < len(ruta):
        if ruta.startswith("${", i):
            prof, j = 0, i + 1
            while j < len(ruta):
                if ruta[j] == "{":
                    prof += 1
                elif ruta[j] == "}":
                    prof -= 1
                    if prof == 0:
                        break
                j += 1
            dentro = ruta[i + 2 : j]
            salida.append("" if "?" in dentro else ":x")
            i = j + 1
        else:
            salida.append(ruta[i])
            i += 1
    limpia = "".join(salida).split("?")[0].rstrip("/")
    return re.sub(r"\{[^}]*\}", ":x", limpia)


# ---------------------------------------------------------------- backend

DECORADOR = re.compile(r"@router\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)['\"]")


def ficheros_de_endpoints() -> list[Path]:
    """Los módulos de endpoints: los ficheros sueltos y los de cada paquete."""
    base = BACK / "api" / "v1" / "endpoints"
    salida = [p for p in sorted(base.glob("*.py")) if not p.stem.startswith("_")]
    for carpeta in sorted(d for d in base.iterdir() if d.is_dir() and d.name != "__pycache__"):
        salida += sorted(carpeta.glob("*.py"))
    return salida


def prefijos() -> dict[str, str]:
    """Módulo de endpoints -> prefijo con el que lo monta el router."""
    texto = leer(BACK / "api" / "v1" / "router.py")
    mapa = {}
    for modulo, resto in re.findall(r"include_router\(\s*(\w+)\.router,([^)]*)\)", texto, re.S):
        p = re.search(r'prefix=\s*"([^"]*)"', resto)
        mapa[modulo] = p.group(1) if p else ""
    return mapa


def modulo_de(p: Path) -> str:
    return "app." + p.relative_to(BACK).with_suffix("").as_posix().replace("/", ".")


def importaciones_py(p: Path) -> set[str]:
    try:
        arbol = ast.parse(leer(p))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app."):
            out.add(n.module)
        elif isinstance(n, ast.Import):
            out.update(a.name for a in n.names if a.name.startswith("app."))
    return out


GRAFO: dict[str, set[str]] = {}


def grafo_backend() -> dict[str, set[str]]:
    if GRAFO:
        return GRAFO
    for p in BACK.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        GRAFO[modulo_de(p)] = importaciones_py(p)
    return GRAFO


def fichero_de_modulo(modulo: str) -> Path | None:
    resto = modulo.removeprefix("app.").replace(".", "/")
    for cand in (BACK / f"{resto}.py", BACK / resto / "__init__.py"):
        if cand.exists():
            return cand
    return None


ARBOLES: dict[str, ast.Module | None] = {}


def arbol(modulo: str) -> ast.Module | None:
    if modulo not in ARBOLES:
        f = fichero_de_modulo(modulo)
        try:
            ARBOLES[modulo] = ast.parse(leer(f)) if f else None
        except SyntaxError:
            ARBOLES[modulo] = None
    return ARBOLES[modulo]


def definiciones(modulo: str) -> dict[str, ast.AST]:
    """Nombre de nivel superior -> su nodo, para poder mirar sólo ese."""
    a = arbol(modulo)
    if a is None:
        return {}
    out: dict[str, ast.AST] = {}
    for n in a.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = n
        elif isinstance(n, ast.Assign):
            for d in n.targets:
                if isinstance(d, ast.Name):
                    out[d.id] = n
    return out


def enlaces(modulo: str) -> dict[str, tuple[str, str]]:
    """Nombre local -> (módulo de origen, nombre allí), sólo dentro de app/."""
    a = arbol(modulo)
    if a is None:
        return {}
    out: dict[str, tuple[str, str]] = {}
    for n in ast.walk(a):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app."):
            for alias in n.names:
                out[alias.asname or alias.name] = (n.module, alias.name)
    return out


def nombres_usados(nodo: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)}


def alcance_py(semillas: set[tuple[str, str]], tope: int = 4000) -> set[tuple[str, str]]:
    """De (módulo, símbolo) a todo lo que ese símbolo alcanza de verdad.

    Por módulo no sirve: `endpoints/teams.py` importa `deps`, y `deps` acaba
    tocando los modelos, y los modelos tocan todo. Mirando sólo el cuerpo de
    la función que atiende la ruta, cada ruta se queda con lo suyo.
    """
    vistos: set[tuple[str, str]] = set()
    pendiente = list(semillas)
    while pendiente and len(vistos) < tope:
        par = pendiente.pop()
        if par in vistos:
            continue
        vistos.add(par)
        modulo, nombre = par
        defs = definiciones(modulo)
        nodo = defs.get(nombre)
        if nodo is None:
            # No lo define: puede que lo reexporte, como hace el `__init__.py`
            # de `endpoints/analysis/` con `roster`. Sin seguirlo, la cadena se
            # corta ahí y `/league`, `/cup` y `/economy` perdían un motor y
            # ocho tests sin que nada avisara: la misma ceguera que las
            # fachadas del frontend, en Python.
            origen = enlaces(modulo).get(nombre)
            if origen and origen != par:
                pendiente.append(origen)
            continue
        usados = nombres_usados(nodo)
        binds = enlaces(modulo)
        for u in usados:
            if u in binds:
                pendiente.append(binds[u])
            elif u in defs and (modulo, u) not in vistos:
                pendiente.append((modulo, u))
    return vistos


def tests_por_simbolo() -> dict[tuple[str, str], set[str]]:
    """(módulo, símbolo) -> tests que lo importan por su nombre."""
    mapa: dict[tuple[str, str], set[str]] = defaultdict(set)
    for p in sorted(TESTS.rglob("test_*.py")):
        try:
            a = ast.parse(leer(p))
        except SyntaxError:
            continue
        rel = p.relative_to(RAIZ / "backend").as_posix()
        for n in ast.walk(a):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app."):
                for alias in n.names:
                    mapa[(n.module, alias.name)].add(rel)
    return mapa


# ------------------------------------------------------------------ main


def rutas_declaradas() -> tuple[dict[str, dict[str, str]], dict[str, list[str]]]:
    """Ruta HTTP -> quién la atiende, y las rutas de cada módulo montado.

    Vive aparte porque la usan dos: el índice, para seguir desde el manejador
    hacia el dominio, y `test_indice.py`, para comprobar que toda ruta que el
    frontend pide la declara alguien. Duplicarla fue un error: al partir
    `analysis.py` en un paquete, el índice aprendió a entrar y el test no, y
    falló por su propia copia vieja.
    """
    pref = prefijos()
    endpoints: dict[str, dict[str, str]] = {}
    por_modulo: dict[str, list[str]] = defaultdict(list)
    for p in ficheros_de_endpoints():
        if p.stem.startswith("_") and p.name != "__init__.py":
            continue
        modulo = modulo_de(p)
        corto = p.parent.name if p.name == "__init__.py" else p.stem
        montado = p.parent.name if p.parent.name != "endpoints" else p.stem
        a = arbol(modulo)
        if a is None:
            continue
        for n in a.body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in n.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)):
                    continue
                if fn.value.id != "router" or not dec.args:
                    continue
                arg = dec.args[0]
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                    continue
                completa = pref.get(montado, "") + arg.value
                endpoints[normalizar(completa)] = {
                    "modulo_corto": corto,
                    "modulo": modulo,
                    "fichero": p.relative_to(RAIZ).as_posix(),
                    "handler": n.name,
                    "metodo": fn.attr.upper(),
                }
                por_modulo[montado].append(f"{fn.attr.upper()} {completa}")
    return endpoints, por_modulo


def recoger() -> dict:
    rutas = rutas_de_app()
    comp2f = fichero_de_componente()
    api = api_a_rutas()
    donde = miembro_a_fichero()
    t_por_sim = tests_por_simbolo()

    # Ruta HTTP -> quién la atiende, con nombre y todo: la semilla del recorrido.
    #
    # Hay endpoints que son un fichero y otros que son un paquete --`analysis/`
    # se partió por funcionalidad-- y hace falta entrar en los dos: si no, las
    # rutas del paquete parecen no existir y las pantallas que las piden salen
    # huérfanas.
    endpoints, por_modulo = rutas_declaradas()

    # --- primera pasada: qué alcanza cada ruta
    crudo = []
    for ruta, comp in rutas:
        f = comp2f.get(comp)
        if not f or not f.exists():
            continue
        fns, tocados = alcance(f)
        httpr = sorted({normalizar(r) for fn in fns for r in api.get(fn, [])})
        atendidas = [endpoints[r] for r in httpr if r in endpoints]
        crudo.append(
            {
                "ruta": "/" + ruta,
                "comp": comp,
                "fichero": f.relative_to(RAIZ).as_posix(),
                "lineas": lineas(f),
                "api": sorted(fns & set(api)),
                "cliente": sorted({donde[f] for f in fns if f in donde}),
                "http": httpr,
                "endpoints": sorted({e["fichero"] for e in atendidas}),
                "pares": alcance_py({(e["modulo"], e["handler"]) for e in atendidas}),
                "locales": sorted(
                    t.relative_to(RAIZ).as_posix() for t in tocados if t != f and FRONT in t.parents
                ),
            }
        )

    # --- segunda pasada: apartar lo que toca TODO el mundo
    #
    # `get_session`, `settings`, el jwt y los modelos salen en las 28 rutas.
    # Si se listan en cada una, cada fila trae 60 ficheros y el índice vuelve
    # a costar lo que costaba leer el repo. Van una sola vez, en su apartado.
    con_datos = [c for c in crudo if c["http"]]
    cuenta: Counter[tuple[str, str]] = Counter()
    for c in con_datos:
        cuenta.update(c["pares"])
    # El 90%, no el 60%: con el 60% caían también las consultas de plantilla,
    # que 19 rutas usan porque los jugadores salen en casi todas, y entonces
    # `/team` --cuya única razón de ser ES la plantilla-- aparecía vacía.
    umbral = max(2, int(len(con_datos) * 0.9))
    comunes = {par for par, n in cuenta.items() if n >= umbral}
    rutas_por_modulo: Counter[str] = Counter()
    for c in con_datos:
        rutas_por_modulo.update({m for m, _ in c["pares"] - comunes})

    datos = []
    for c in crudo:
        propios = c["pares"] - comunes
        modulos = {m for m, _ in propios}
        datos.append(
            {
                **{k: v for k, v in c.items() if k != "pares"},
                "aplicacion": sorted(m for m in modulos if m.startswith("app.application")),
                "dominio": sorted(m for m in modulos if m.startswith("app.domain")),
                "infraestructura": sorted(m for m in modulos if m.startswith("app.infrastructure")),
                "tests": sorted({t for par in propios for t in t_por_sim.get(par, set())}),
                "simbolos": len(propios),
            }
        )

    transversal = sorted({m for m, _ in comunes})
    tests_generales = sorted({t for par in comunes for t in t_por_sim.get(par, set())})
    return {
        "rutas": datos,
        "endpoints": dict(por_modulo),
        "transversal": transversal,
        "tests_generales": tests_generales,
        "compartidos": {m: n for m, n in rutas_por_modulo.most_common() if n >= 5},
        "umbral": umbral,
        "de": len(con_datos),
    }


# ------------------------------------------------------------- el documento


def cabecera(d: dict) -> list[str]:
    return [
        "# Índice del código por funcionalidad",
        "",
        "**Generado. No se edita a mano:** `python backend/scripts/indice.py`.",
        "",
        "Para qué sirve: para cambiar una pantalla hay que saber primero qué",
        "ficheros la forman, y averiguarlo leyendo el repo cuesta más que el",
        "cambio. Aquí está la cadena entera de cada ruta, sacada de las",
        "importaciones y de los decoradores, no de lo que alguien recuerde.",
        "",
        "Cómo se usa: busca tu ruta en la tabla, abre su apartado, y abre sólo",
        "los ficheros que lista. Lo que no esté ahí no hace falta leerlo.",
        "",
        "Aviso sobre los documentos vecinos: `05-frontend.md` y",
        "`01-arquitectura.md` describen un Next.js con Celery que nunca se",
        "construyó, y `68-catalogo-vistas.md` y `200-vistas-y-tabs.md` son",
        "planes, no código. Para orientarse, este fichero; ésos, para historia.",
        "",
        "## Cómo se calcula",
        "",
        "Por **símbolo**, no por fichero, que es lo que lo hace útil:",
        "`useTeam.ts` tiene 60 hooks y `services/api.ts` 66 miembros, así que",
        "contar por fichero ataría cada pantalla a media aplicación. Se mira el",
        "cuerpo del hook que se importó y el cuerpo de la función que atiende",
        "la ruta, y se sigue desde ahí.",
        "",
        f"Lo que alcanzan {d['umbral']} de las {d['de']} rutas o más se considera",
        "fontanería compartida y se aparta en «Transversal», al final: si no se",
        "apartara, cada fila traería sesenta ficheros y no serviría de nada.",
        "",
    ]


def tabla(d: dict) -> list[str]:
    out = [
        "## Las funcionalidades",
        "",
        "`Leer` es el total de líneas de TODO lo que hay que abrir para tocar esa",
        "pantalla: la página, sus componentes, su cliente, su endpoint, su",
        "aplicación y sus motores. Es la cuenta que conviene ver bajar.",
        "",
        "| Ruta | Página | Líneas | Leer | Endpoints | Dominio | Tests |",
        "| --- | --- | --: | --: | --- | --: | --: |",
    ]
    for r in d["rutas"]:
        pag = r["fichero"].replace("frontend/src/pages/", "")
        ends = ", ".join(Path(e).stem for e in r["endpoints"]) or "-"
        out.append(
            f"| `{r['ruta']}` | [{pag}]({ruta_rel(r['fichero'])}) | {r['lineas']} "
            f"| {coste_de_ruta(r) if r['http'] else '-'} "
            f"| {ends} | {len(r['dominio'])} | {len(r['tests'])} |"
        )
    out.append("")
    return out


def ruta_rel(p: str) -> str:
    return "../" + p


def bloques(d: dict) -> list[str]:
    comp = d.get("compartidos", {})
    out = ["## Ruta por ruta", ""]
    for r in d["rutas"]:
        out.append(f"### `{r['ruta']}`")
        out.append("")
        out.append(
            f"- **Página:** [{r['fichero']}]({ruta_rel(r['fichero'])}) ({r['lineas']} líneas)"
        )
        if r["locales"]:
            out.append(f"- **Componentes y hooks suyos ({len(r['locales'])}):**")
            for loc in r["locales"]:
                out.append(f"  - [{loc}]({ruta_rel(loc)})")
        if r["api"]:
            out.append(f"- **Pide a `api.`:** {', '.join('`' + a + '`' for a in r['api'])}")
        if r.get("cliente"):
            enlaces = ", ".join(f"[{c}]({ruta_rel(c)})" for c in r["cliente"])
            out.append(f"- **Donde se escriben esas llamadas:** {enlaces}")
        if r["http"]:
            out.append(f"- **Rutas HTTP:** {', '.join('`' + h + '`' for h in r['http'])}")
        for titulo, clave in (
            ("Endpoints", "endpoints"),
            ("Aplicación", "aplicacion"),
            ("Dominio", "dominio"),
            ("Infraestructura", "infraestructura"),
        ):
            if r.get(clave):
                if clave == "endpoints":
                    vals = [f"[{m}]({ruta_rel(m)})" for m in r[clave]]
                else:
                    # El número avisa del radio: cambiar algo que usan 19 rutas
                    # no es lo mismo que cambiar algo que usa sólo ésta.
                    vals = [
                        f"`{m}`" + (f" ({comp[m]} rutas)" if m in comp else "") for m in r[clave]
                    ]
                out.append(f"- **{titulo}:** {', '.join(vals)}")
        if r["tests"]:
            out.append(
                f"- **Tests ({len(r['tests'])}):** {', '.join('`' + t + '`' for t in r['tests'])}"
            )
        if not r["http"]:
            out.append("- Sin datos del servidor: esta pantalla no pide nada al backend.")
        out.append("")
    return out


def transversal(d: dict) -> list[str]:
    out = [
        "## Transversal",
        "",
        f"Lo que alcanzan {d['umbral']} de {d['de']} rutas o más. Tocar aquí es tocar",
        "toda la aplicación, así que conviene mirar antes qué rutas dependen de",
        "ello, y correr los tests generales enteros.",
        "",
    ]
    for m in d["transversal"]:
        out.append(f"- `{m}`")
    out.append("")
    out.append(
        "**Tests que cubren esa parte compartida "
        f"({len(d['tests_generales'])}):** correrlos al tocarla."
    )
    out.append("")
    return out


def ficheros_de_ruta(r: dict) -> set[str]:
    """Todo lo que hay que abrir para tocar una pantalla."""
    out = set(r["locales"]) | {r["fichero"]} | set(r.get("cliente", [])) | set(r["endpoints"])
    for m in r["aplicacion"] + r["dominio"] + r["infraestructura"]:
        f = fichero_de_modulo(m)
        if f:
            out.add(f.relative_to(RAIZ).as_posix())
    return out


def coste_de_ruta(r: dict) -> int:
    return sum(lineas(RAIZ / f) for f in ficheros_de_ruta(r))


def costosos(d: dict) -> list[str]:
    """Qué conviene partir, medido: tamaño por número de rutas que lo abren.

    El tamaño a secas engaña. `useTeam.ts` tiene 601 líneas y sale más caro
    que ficheros de mil quinientas, porque lo abren 26 de las 31 pantallas;
    y un fichero enorme que sólo lee una pantalla no estorba a nadie.
    """
    peso: Counter[str] = Counter()
    for r in d["rutas"]:
        if not r["http"]:
            continue
        ficheros = set(r["locales"]) | {r["fichero"]} | set(r.get("cliente", []))
        ficheros |= set(r["endpoints"])
        for m in r["aplicacion"] + r["dominio"] + r["infraestructura"]:
            f = fichero_de_modulo(m)
            if f:
                ficheros.add(f.relative_to(RAIZ).as_posix())
        peso.update(ficheros)

    filas = []
    for f, n in peso.items():
        largo = lineas(RAIZ / f)
        filas.append((largo * n, largo, n, f))
    filas.sort(reverse=True)

    out = [
        "## Qué conviene partir",
        "",
        "`coste` es las líneas por el número de pantallas que abren el fichero:",
        "lo que cuesta de verdad no es lo grande que sea, sino lo grande por lo",
        "a menudo que hay que leerlo. Un fichero enorme que sólo lee una",
        "pantalla no estorba; uno mediano que leen veintiséis, sí.",
        "",
        "| Coste | Líneas | Pantallas | Fichero |",
        "| --: | --: | --: | --- |",
    ]
    for coste, largo, n, f in filas[:20]:
        out.append(f"| {coste} | {largo} | {n} | [{f}]({ruta_rel(f)}) |")
    out.append("")
    return out


def main() -> None:
    d = recoger()
    (RAIZ / "docs" / "indice.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    texto = "\n".join(cabecera(d) + tabla(d) + bloques(d) + transversal(d) + costosos(d))
    (RAIZ / "docs" / "INDICE.md").write_text(texto, encoding="utf-8")
    print(
        f"docs/INDICE.md · rutas {len(d['rutas'])} · endpoints {len(d['endpoints'])} "
        f"· módulos {len(grafo_backend())} · transversal {len(d['transversal'])}"
    )
    for r in d["rutas"]:
        print(
            f"  {r['ruta']:<22} http={len(r['http']):<2} "
            f"end={','.join(Path(e).stem for e in r['endpoints']) or '-':<24} "
            f"apl={len(r['aplicacion']):<2} dom={len(r['dominio']):<2} tests={len(r['tests'])}"
        )


if __name__ == "__main__":
    main()
