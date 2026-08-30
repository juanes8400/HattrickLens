"""Juveniles. HL-110, HL-111, HL-112, HL-114, HL-115."""

from dataclasses import asdict, replace
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.academy import AcademyQueryService
from app.domain.engines import decision_individual as di
from app.domain.engines import metodo_cinco as m5
from app.domain.engines import reparto_por_descubrimiento as rpd
from app.domain.engines import youth_skill_score as yss
from app.domain.engines.youth_training_plan import (
    ENTRENAMIENTOS,
    REGION_AMBOS,
    REGION_SIN_ENTRENAMIENTO,
    REGION_SOLO_PRINCIPAL,
    RITMO_INDIVIDUAL_DUDOSO,
    Asignacion,
    factor_secundario,
    mejor_variante,
    youth_training_plan,
)
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/academy",
    summary="Canteranos, plazos y retorno de la academia",
    dependencies=[Depends(require_team_owner)],
)
async def academy(team_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Cruza lo invertido con lo ingresado, que es lo que nadie cruza.

    El gasto de la academia es semanal y silencioso y el retorno llega
    temporadas después, en otra pantalla. Aquí van juntos. Y un techo que el
    ojeador no ha revelado se trata como desconocido, no como bajo: descartar
    una promesa por falta de información sería confundir ignorancia con
    evidencia.
    """
    data = await AcademyQueryService(session).get(team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return cast(dict[str, Any], _camel(asdict(data)))


#: A que columna del banquillo va cada uno, por la habilidad en la que mas
#: destaca. Hattrick no le asigna puesto a un juvenil, asi que esto es una
#: lectura: quien apunta a defensa se sienta con los defensas.
COLUMNA_POR_HABILIDAD: dict[str, str] = {
    "keeper": "Portero",
    "defending": "Defensa Central",
    "winger": "Extremo",
    "playmaking": "Medio Centro",
    "passing": "Medio Centro",
    "scoring": "Delantero",
}


def _columna_de_banquillo(mejor_habilidad: str | None) -> str:
    """Sin habilidad destacada no hay columna que adivinar: va a «Extra»."""
    return COLUMNA_POR_HABILIDAD.get(mejor_habilidad or "", "Extra")


def _sin_revelar_por_jugador(rows: list[Any]) -> dict[str, int]:
    """Cuantas de las cinco habilidades de puesto no se saben, por canterano.

    Es lo que ordena la cola de «Individual». Un techo ya alcanzado no cuenta
    como hueco: entrenarlo no lo va a revelar, asi que ponerlo delante seria
    gastar la plaza en alguien que no puede iluminar nada.
    """
    cuenta: dict[str, int] = {}
    for fila in rows:
        if fila.skill not in di.HABILIDADES_DE_PUESTO:
            continue
        for p in list(fila.players) + list(fila.at_max):
            cuenta.setdefault(p.name, 0)
            if p.current is None and not p.max_reached:
                cuenta[p.name] += 1
    return cuenta


#: Los peldanos que cuentan como «lo sabemos Y es bueno». Los de ignorancia
#: (⅓ y ¹⁄₂₇ en la escalera) y el de los que ya tocaron techo quedan fuera a
#: proposito: son justo lo que el metodo 5 quiere distinguir.
_CUBOS_CON_RESPALDO = frozenset(
    {
        yss.Bucket.EXCELLENT,
        yss.Bucket.GOOD_SOON,
        yss.Bucket.GOOD_LATER,
        yss.Bucket.ACCEPTABLE_SOON,
        yss.Bucket.ACCEPTABLE_LATER,
    }
)


def _desmenuza(rows: list[Any], weight_base: float) -> list[m5.Habilidad]:
    """Parte cada puntaje en sus dos mitades: lo que se sabe y lo que no.

    Es la unica cuenta que el metodo 5 necesita y que la fila no trae hecha.
    Se rehace con la MISMA base de pesos que uso el ranking --si no, la niebla
    se calcularia contra una escalera distinta de la que produjo el numero--.
    """
    pesos = yss.weights_for(weight_base)
    salida: list[m5.Habilidad] = []
    for r in rows:
        con = des = 0.0
        valen = 0
        for cubo, n in r.counts.items():
            w = n * pesos.get(cubo, 0.0) / yss.SQUAD_NORMALISER
            if cubo in _CUBOS_CON_RESPALDO:
                con += w
                valen += n
            else:
                des += w
        salida.append(
            m5.Habilidad(
                skill=r.skill,
                label=r.label,
                puntaje=r.score,
                de_saber=con,
                de_no_saber=des,
                cuantos_valen=valen,
            )
        )
    return salida


def _cola_para(clave: str, fila: Any, rows: list[Any]) -> list[Any]:
    """La cola de un entrenamiento. «Individual» ordena por descubrimiento."""
    if clave != di.INDIVIDUAL:
        return list(fila.players)
    todos: dict[str, Any] = {}
    for r in rows:
        for n in r.players:
            todos.setdefault(n.name, n)
    return di.cola_de_descubrimiento(list(todos.values()), _sin_revelar_por_jugador(rows))


def _veredicto_json(v: m5.Veredicto | None) -> dict[str, Any]:
    """El porque, para que la pantalla no tenga que rehacer la cuenta."""
    if v is None:
        return {}
    return {
        "method": {
            "path": v.camino,
            "why": v.motivo,
            "fogMain": round(v.niebla_principal, 3),
            "fogSecond": None if v.niebla_segunda is None else round(v.niebla_segunda, 3),
            "backedMain": v.valen_principal,
        }
    }


def _recoloca_para_descubrir(
    plan: Any,
    main: str,
    secondary: str,
    lecturas: dict[str, dict[str, Any]],
) -> None:
    """Reordena las plazas que NO entrena el compañero, para destapar más.

    Solo actúa cuando «Individual» ocupa un hueco, porque es el único
    entrenamiento cuya habilidad depende del PUESTO: con cualquier otro, mover
    a un chico de plaza no cambia lo que recibe.

    Dos reglas, dictadas por el usuario el 2026-08-26:

    1. **El compañero manda.** Las plazas de la región del otro entrenamiento
       no se tocan: ya las llenó su cola y ese reparto no se negocia.
    2. **La habilidad del compañero NO cuenta como descubrimiento.** Que a un
       chico le salga Lateral cuando Lateral es el principal no aporta nada:
       esa habilidad ya se está trabajando. Se descuenta de la ruleta.

    El emparejamiento es el óptimo real, no por turnos: quitarle el portero a
    quien más lo aprovecha puede costar más de lo que gana quien se lo queda.
    Modifica `plan` en el sitio.
    """
    if di.INDIVIDUAL not in (main, secondary):
        return

    individual = ENTRENAMIENTOS[di.INDIVIDUAL]
    # Lo que el COMPAÑERO ya entrena, que por eso no cuenta como descubrir. Si
    # sube dos --«Anotación y balón parado»-- se descuentan las dos.
    companero = ENTRENAMIENTOS.get(secondary if main == di.INDIVIDUAL else main)
    excluidas: set[str] = set()
    if companero is not None and companero.codigo != di.INDIVIDUAL:
        excluidas.add(companero.skill)
        if companero.tambien_sube:
            excluidas.add(companero.tambien_sube)

    # Las sillas en juego: las que NO pertenecen a la región del compañero.
    # Cuando Individual está en los dos huecos, todas lo están.
    if main == secondary == di.INDIVIDUAL:
        libres = [a for a in plan.asignaciones if a.puesto]
    else:
        del_companero = {REGION_AMBOS, REGION_SOLO_PRINCIPAL}
        libres = [a for a in plan.asignaciones if a.puesto and a.region not in del_companero]
    if not libres:
        return

    # Los candidatos: quien ocupa esas sillas MÁS el banquillo. Limitarlo a
    # los que ya estaban dentro dejaría fuera al chico del banquillo que
    # ilumina más que cualquiera de los de dentro.
    en_juego = {a.player for a in libres}
    candidatos: list[rpd.Candidato] = []
    for nombre in list(en_juego) + [a.player for a in plan.fuera if a.player not in en_juego]:
        skills = lecturas.get(nombre, {})
        candidatos.append(
            rpd.Candidato(
                nombre=nombre,
                sin_revelar=frozenset(
                    sk for sk, r in skills.items() if r.current is None and not r.max_reached
                ),
            )
        )

    ruletas = {a.puesto: individual.reparto_en(a.puesto) for a in libres}
    pares = rpd.reparte([a.puesto for a in libres], candidatos, ruletas, excluidas)
    if len(pares) != len(libres):
        return  # no se pudo llenar todo: mejor dejarlo como estaba

    # Se reescribe solo el nombre de cada silla; el resto de la fila --puesto,
    # región, raciones-- describe LA PLAZA y no cambia al cambiar de ocupante.
    # `Asignacion` es inmutable, así que se sustituye la fila entera en su
    # sitio en vez de tocarla.
    banquillo = {a.player: a for a in plan.fuera}
    dentro_antes = {a.player for a in libres}
    por_id = {id(a): i for i, a in enumerate(plan.asignaciones)}
    nuevas: list[Any] = []
    for silla, (nombre, _) in zip(libres, pares, strict=True):
        cambiada = replace(silla, player=nombre)
        plan.asignaciones[por_id[id(silla)]] = cambiada
        nuevas.append(cambiada)
    libres = nuevas
    # Quien salió del once y quien entró: el banquillo se recalcula para no
    # enseñar a nadie dos veces.
    dentro_ahora = {a.player for a in libres}
    for nombre in dentro_ahora - dentro_antes:
        if nombre in banquillo:
            plan.fuera.remove(banquillo[nombre])
    for nombre in dentro_antes - dentro_ahora:
        plan.fuera.append(
            Asignacion(
                player=nombre,
                puesto="",
                region=REGION_SIN_ENTRENAMIENTO,
                racion_principal=0.0,
                racion_secundaria=0.0,
            )
        )


def _pareja_sugerida(
    rows: list[Any],
    *,
    weight_base: float = yss.DEFAULT_WEIGHT_BASE,
    niebla_maxima: float = m5.NIEBLA_MAXIMA,
    minimo_para_doblar: int = m5.MINIMO_PARA_DOBLAR,
) -> dict[str, Any] | None:
    """Que entrenar de principal y de secundario, con la forma que encaja.

    Desde el 2026-08-26 «Individual» puede ganar cualquiera de los dos huecos.
    Las dos reglas viven en `decision_individual` y son puramente numericas
    --ver alli el porque--; aqui solo se traducen a la misma respuesta de
    siempre. La pantalla no se entera: recibe los mismos campos y pinta lo que
    le llega, que era la condicion del usuario.
    """
    if len(rows) < 2:
        return None
    veredicto = m5.decidir(
        _desmenuza(rows, weight_base),
        niebla_maxima=niebla_maxima,
        minimo_para_doblar=minimo_para_doblar,
    )
    por_skill = {r.skill: r for r in rows}
    principal = por_skill.get(veredicto.principal, rows[0]) if veredicto else rows[0]
    segunda = por_skill.get(veredicto.secundario, rows[1]) if veredicto else rows[1]

    if veredicto is not None and veredicto.descubre:
        individual = ENTRENAMIENTOS[di.INDIVIDUAL]
        # Regla B pone Individual en los dos huecos; la A solo en el segundo y
        # deja el principal donde estaba.
        clave_main = di.INDIVIDUAL if veredicto.principal == di.INDIVIDUAL else principal.skill
        fila_main = principal
        plan = youth_training_plan(
            clave_main,
            di.INDIVIDUAL,
            _cola_para(clave_main, fila_main, rows),
            _cola_para(di.INDIVIDUAL, segunda, rows),
            tope_principal=(
                set() if clave_main == di.INDIVIDUAL else {p.name for p in principal.at_max}
            ),
            # Individual no veta a nadie: quien toco techo en la habilidad de
            # un puesto sigue sirviendo en cualquier otro.
            tope_secundaria=set(),
        )
        return {
            "main": clave_main,
            "mainLabel": individual.label if clave_main == di.INDIVIDUAL else principal.label,
            "secondary": di.INDIVIDUAL,
            "secondaryLabel": individual.label,
            "secondarySkill": "",
            "bothCount": plan.con_doble,
            **_veredicto_json(veredicto),
        }

    codigo = mejor_variante(principal.skill, segunda.skill)
    variante = ENTRENAMIENTOS.get(codigo)
    # El reparto de verdad, no el solape de PUESTOS: la frase promete un
    # numero y al pulsar el boton se ve la cancha, y los dos tienen que decir
    # lo mismo. Un puesto de la interseccion que nadie ocupa no es una racion
    # doble.
    plan = youth_training_plan(
        principal.skill,
        codigo,
        principal.players,
        segunda.players,
        tope_principal={p.name for p in principal.at_max},
        tope_secundaria={p.name for p in segunda.at_max},
    )
    return {
        "main": principal.skill,
        "mainLabel": principal.label,
        "secondary": codigo,
        "secondaryLabel": variante.label if variante else segunda.label,
        "secondarySkill": segunda.skill,
        # Cuantos recibirian las dos cosas con esa pareja, y por cuantas
        # semanas: es lo que justifica elegir una forma y no otra.
        "bothCount": plan.con_doble,
        **_veredicto_json(veredicto),
    }


def _cobertura_del_ojeador(rows: list[Any]) -> dict[str, Any]:
    """Cuantas lecturas ha dado el ojeador, de todas las que hay.

    Una lectura es un par jugador-habilidad. Cuenta como revelada si se sabe
    el nivel, el techo, o que ya toco techo --las tres son informacion--.
    """
    revelados = total = 0
    en_blanco: dict[str, int] = {}
    for fila in rows:
        for p in list(fila.players) + list(fila.at_max):
            total += 1
            if p.current is not None or p.maximum is not None or p.max_reached:
                revelados += 1
            else:
                en_blanco[p.name] = en_blanco.get(p.name, 0) + 1
    # Un canterano "en blanco" es el que no tiene NI UNA lectura en las siete.
    sin_nada = sorted(n for n, cuantas in en_blanco.items() if cuantas == len(yss.SKILLS))
    return {"known": revelados, "total": total, "blankPlayers": sin_nada}


@router.get(
    "/teams/{team_id}/academy/training-plan",
    summary="El once juvenil con los dos entrenamientos repartidos",
    dependencies=[Depends(require_team_owner)],
)
async def academy_training_plan(
    team_id: int,
    main: str = Query(..., description="Entrenamiento principal"),
    secondary: str = Query(..., description="Entrenamiento secundario"),
    soon_max_days: int = Query(yss.SOON_MAX_DAYS, ge=0, le=112),
    weight_base: float = Query(
        yss.DEFAULT_WEIGHT_BASE, ge=yss.MIN_WEIGHT_BASE, le=yss.MAX_WEIGHT_BASE
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Quién ocupa cada plaza cuando se entrenan dos cosas a la vez.

    Los dos entrenamientos dibujan un diagrama de Venn sobre los PUESTOS del
    campo. La intersección --los que reciben los dos-- se llena primero
    con los mejores del principal; ver `youth_training_plan`.
    """
    for nombre, valor in (("main", main), ("secondary", secondary)):
        # Vale una habilidad a secas --«passing»-- o un entrenamiento concreto
        # --«passing_defenders»--: la sugerencia manda el segundo.
        if valor not in yss.SKILLS and valor not in ENTRENAMIENTOS:
            raise HTTPException(422, f"{nombre}: «{valor}» no es un entrenamiento")

    service = AcademyQueryService(session)
    rows = await service.skill_scores(
        team_id,
        soon_max_days=soon_max_days,
        weight_base=weight_base,
    )
    if rows is None:
        raise HTTPException(404, f"team {team_id} sin canteranos")
    por_habilidad = {r.skill: r for r in rows}

    #: Que no sabemos todavia de cada canterano. Se declara VACIO aqui y se
    #: llena mas abajo, en cuanto la academia esta cargada: `habilidad_de` lo
    #: cierra por referencia, asi que rellenar el mismo diccionario basta y no
    #: hay que partir la funcion en dos. Las llamadas de antes no lo tocan
    #: --pasan sin jugador y cortocircuitan--.
    sin_saber: dict[str, set[str]] = {}

    def habilidad_de(clave: str, puesto: str = "", jugador: str = "") -> str:
        """Que habilidad sube ese entrenamiento, en esa plaza, para ese chico.

        `puesto` y `jugador` solo los usa «Individual», que SORTEA una entre
        las utiles del puesto en vez de subir siempre la misma; los demas los
        ignoran. Preguntar siempre con los tres deja el resto del endpoint sin
        un solo `if` sobre Individual.

        Con `jugador` se elige la mas probable DE LAS QUE NO SE SABEN: la
        plaza esta ahi para descubrir, y anunciar una habilidad ya revelada no
        dice nada.
        """
        e = ENTRENAMIENTOS.get(clave)
        if e is None:
            return clave
        return e.skill_en(puesto, sin_saber.get(jugador) if jugador else None)

    skill_main, skill_sec = habilidad_de(main), habilidad_de(secondary)
    # «Individual» no tiene UNA habilidad --cada puesto sube la suya-- asi que
    # se le exime de esta comprobacion. Todo lo demas lo trata igual que a
    # cualquier otro entrenamiento.
    for clave, skill in ((main, skill_main), (secondary, skill_sec)):
        if clave != di.INDIVIDUAL and skill not in por_habilidad:
            raise HTTPException(404, "no hay canteranos con esas habilidades")

    academia = await service.get(team_id)
    # Un techo alcanzado NO es un hueco: ya se sabe que no sube, asi que
    # entrenarlo no revela nada y no debe atraer una plaza de descubrimiento.
    sin_saber.update(
        {
            j.name: {r.skill for r in j.skills if not r.is_current_known and not r.max_reached}
            for j in (academia.players if academia else [])
        }
    )
    mejores = {j.name: j.best_skill for j in (academia.players if academia else [])}
    # Las siete lecturas de cada canterano, para poder ensenar en la tabla el
    # nivel de LAS DOS habilidades que se entrenan --no solo la que le dio la
    # plaza-- y donde le queda techo por descubrir.
    lecturas = {
        j.name: {r.skill: r for r in j.skills} for j in (academia.players if academia else [])
    }

    # Cuantas de las cinco habilidades de puesto no se saben todavia de cada
    # canterano. Es lo que ordena la cola de «Individual»: quien mas ilumina,
    # primero. Un techo ya alcanzado NO cuenta como hueco --entrenarlo no lo
    # va a revelar-- y por eso se descuenta aqui y no despues.
    sin_revelar = {
        j.name: sum(
            1
            for r in j.skills
            if r.skill in di.HABILIDADES_DE_PUESTO and not r.is_current_known and not r.max_reached
        )
        for j in (academia.players if academia else [])
    }
    # Un `PlayerNote` por canterano, venga de la habilidad que venga: para
    # ordenar por descubrimiento solo hacen falta los datos comunes --nombre,
    # plazo, potencial--. Se recorren todas las habilidades porque cada cola
    # deja fuera a los que tocaron techo EN ELLA, y aqui no puede faltar nadie.
    todos_los_notas: dict[str, Any] = {}
    for fila in rows:
        for n in fila.players:
            todos_los_notas.setdefault(n.name, n)

    def cola_de(clave: str, skill: str) -> list[Any]:
        if clave == di.INDIVIDUAL:
            return di.cola_de_descubrimiento(list(todos_los_notas.values()), sin_revelar)
        return list(por_habilidad[skill].players)

    def topes_de(clave: str, skill: str) -> set[str]:
        # Individual no veta a nadie: quien tocó techo en la habilidad de un
        # puesto sigue sirviendo en otro, y el veto es por entrenamiento
        # entero, no por plaza. Vetarlo aqui dejaria plazas vacias por una
        # razon que no aplica a todas.
        if clave == di.INDIVIDUAL:
            return set()
        return {p.name for p in por_habilidad[skill].at_max}

    plan = youth_training_plan(
        main,
        secondary,
        cola_de(main, skill_main),
        cola_de(secondary, skill_sec),
        tope_principal=topes_de(main, skill_main),
        tope_secundaria=topes_de(secondary, skill_sec),
    )
    _recoloca_para_descubrir(plan, main, secondary, lecturas)
    etiquetas = {r.skill: r.label for r in rows}

    def etiqueta_de(clave: str, skill: str) -> str:
        e = ENTRENAMIENTOS.get(clave)
        return e.label if e else etiquetas.get(skill, skill)

    def _lectura(nombre: str, skill: str) -> dict[str, Any]:
        r = lecturas.get(nombre, {}).get(skill)
        return {
            "label": etiquetas.get(skill, skill),
            "current": r.current if r else None,
            "maximum": r.maximum if r else None,
            "max_reached": bool(r.max_reached) if r else False,
        }

    def _lineas(clave: str, puesto: str, jugador: str, es_secundario: bool) -> list[dict[str, Any]]:
        """Lo que va en UNA celda de entrenamiento, linea a linea.

        Antes cada celda era un numero. Con «Individual» ese numero pasaba a
        ser una MEDIA, y una media aqui engaña: mezcla un 66,7% de Pases con
        un 28,3% de Lateral como si valieran lo mismo, y esconde lo mas util
        de saber --que en un extremo la habilidad MAS probable es la que PEOR
        entrena--. Asi que la celda se despliega.

        Sale generico: el motor describe un entrenamiento corriente como una
        sola linea, asi que para ellos la pantalla no cambia nada. Y «Anotación
        y balón parado» da sus DOS lineas sin probabilidad, porque no sortea:
        sube las dos siempre.
        """
        entrenamiento = ENTRENAMIENTOS.get(clave)
        if entrenamiento is None:
            return []
        # El castigo cae en el HUECO secundario y compara los entrenamientos,
        # no la habilidad que finalmente salga. Por eso Lateral + Individual
        # conserva ⅔ incluso si la ruleta descubre Lateral; solo Individual +
        # Individual (o cualquier codigo exactamente repetido) baja a ⅓ y da
        # el total acordado de 133,3%.
        castigo = factor_secundario(main, secondary) if es_secundario else 1.0

        return [
            {
                "skill": linea.skill,
                "label": etiquetas.get(linea.skill, linea.skill),
                "rate": round(linea.ritmo * castigo, 1),
                # Lo que rendiria en el hueco PRINCIPAL, sin castigo. La
                # pantalla lo necesita para poder decir de donde sale el
                # numero: «28,3%» a secas no deja ver que ya son dos tercios
                # de 42,5, y el mismo sorteo vale 42,5 / 28,3 / 14,2 segun el
                # hueco. Sin esto la cifra es ambigua.
                "base": round(linea.ritmo, 1),
                # El estudio de la comunidad NO midio dos de las siete
                # --Porteria y Balon parado, que el autor marca «?» y
                # «guess!»-- y en un PORTERO eso son dos de sus tres lineas.
                # Se dice, porque leer como medido lo que es conjetura es
                # peor que no tener el numero.
                "uncertain": linea.skill in RITMO_INDIVIDUAL_DUDOSO
                and entrenamiento.distribucion_por_puesto is not None,
                "penalty": round(castigo, 4),
                # None significa «esto pasa siempre», no «no se sabe»: la
                # pantalla usa eso para poner o quitar el «(proba: N%)».
                "probability": linea.probabilidad,
                # El nivel de ESTA habilidad. Es lo que convierte la linea en
                # una decision: una salida en «desconocido» al 21% es una
                # apuesta, y una ya revelada al 34% es entrenamiento tirado.
                "level": _lectura(jugador, linea.skill),
            }
            for linea in entrenamiento.lineas_en(puesto)
        ]

    def _con_habilidad(a: Any) -> dict[str, Any]:
        skill = habilidad_de(a.elegido_por, a.puesto, a.player)
        # Donde todavia puede crecer sin que nadie sepa cuanto: el techo sin
        # revelar es la unica pista de potencial que queda. Si ya no queda
        # ninguno, es que el ojeador termino con el.
        sin_techo = [
            etiquetas.get(sk, sk)
            for sk, r in lecturas.get(a.player, {}).items()
            if r.maximum is None and not r.max_reached
        ]
        return {
            **asdict(a),
            "skill_label": etiquetas.get(skill, skill),
            # Con puesto: en «Individual» la columna «Nivel» tiene que ser
            # la de la habilidad que ESA plaza entrena, no la de una habilidad
            # fija que ahi no significa nada.
            "main_level": _lectura(a.player, habilidad_de(main, a.puesto, a.player)),
            "secondary_level": _lectura(a.player, habilidad_de(secondary, a.puesto, a.player)),
            "open_ceilings": sin_techo,
            "main_lines": _lineas(main, a.puesto, a.player, es_secundario=False),
            "secondary_lines": _lineas(secondary, a.puesto, a.player, es_secundario=True),
        }

    return cast(
        dict[str, Any],
        _camel(
            {
                "main": main,
                "mainLabel": etiqueta_de(main, skill_main),
                "secondary": secondary,
                "secondaryLabel": etiqueta_de(secondary, skill_sec),
                # El contrato publica la regla que ya usaron todas las filas.
                # Así la interfaz no vuelve a escribir su propia versión del
                # 2/3 o del 1/3 y no puede separarse del motor.
                "secondaryFactor": factor_secundario(main, secondary),
                "combinedFactor": 1 + factor_secundario(main, secondary),
                "repeatedTraining": main == secondary,
                "doubleCount": plan.con_doble,
                "doubleBlind": plan.doble_a_ciegas,
                # Cuanto ha revelado el ojeador en toda la academia. Sin esto la
                # cancha llena de "desconocido" parece un fallo nuestro, y es el
                # estado real: aqui casi nada esta revelado todavia.
                "scouting": _cobertura_del_ojeador(rows),
                # `skillLabel` es DE QUE habilidad es el nivel que lleva cada fila:
                # cambia por region --la principal arriba, la secundaria en su
                # tramo-- y sin decirlo la columna "Nivel" no significa nada.
                "assignments": [_con_habilidad(a) for a in plan.asignaciones],
                # El banquillo: los que no entraron, con lo mismo que llevan los de
                # dentro y la columna en que caen. Un juvenil no tiene puesto asignado
                # en Hattrick, asi que la columna sale de la habilidad en la que mas
                # destaca --es una lectura nuestra, no un dato del juego.
                "outside": [
                    {
                        **_con_habilidad(a),
                        "benchColumn": _columna_de_banquillo(mejores.get(a.player)),
                    }
                    for a in plan.fuera
                ],
            }
        ),
    )


@router.get(
    "/teams/{team_id}/academy/scouts",
    summary="Quién trajo a cada canterano y qué queda por revelarle",
    dependencies=[Depends(require_team_owner)],
)
async def academy_scouts(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """El informe del ojeador, tal cual lo escribió.

    CHPP no publica una lista de ojeadores --`youthscouts`, `youthscoutlist` y
    `scouts` devuelven 401--, así que lo único que existe es el `ScoutCall` de
    cada canterano: quién lo encontró, dónde estaba ojeando y qué dijo. Con
    eso se puede agrupar por ojeador, que es lo más parecido a "mis
    ojeadores" que hay.
    """
    import json as _json

    from sqlalchemy import select

    from app.application.queries.team_overview import SKILL_LABELS
    from app.infrastructure.db import models as m

    filas = (
        await session.execute(
            select(m.YouthPlayer, m.YouthScoutReport)
            .join(
                m.YouthScoutReport,
                m.YouthScoutReport.youth_player_id == m.YouthPlayer.id,
            )
            .where(m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None))
        )
    ).all()

    etiquetas = {s_: SKILL_LABELS.get(s_, s_) for s_ in yss.SKILLS}
    jugadores = []
    for juvenil, informe in filas:
        puede = _json.loads(informe.may_unlock_json or "{}")
        jugadores.append(
            {
                "name": f"{juvenil.first_name} {juvenil.last_name}".strip(),
                "htYouthPlayerId": juvenil.ht_youth_player_id,
                "arrivedAt": juvenil.arrived_at.isoformat() if juvenil.arrived_at else None,
                "scoutId": informe.scout_id,
                "scoutName": informe.scout_name or "sin nombre",
                "scoutingRegionId": informe.scouting_region_id,
                "comments": [c.get("text", "") for c in _json.loads(informe.comments_json or "[]")],
                # A que habilidades les queda algo por revelar, dicho por el juego
                # y no supuesto por nosotros.
                "mayUnlock": [etiquetas[k] for k, v in puede.items() if v and k in etiquetas],
                "fetchedAt": informe.fetched_at.isoformat() if informe.fetched_at else None,
            }
        )
    jugadores.sort(key=lambda j: (j["scoutName"], j["name"]))

    ojeadores: dict[int | None, dict[str, Any]] = {}
    for j in jugadores:
        o = ojeadores.setdefault(
            j["scoutId"],
            {
                "scoutId": j["scoutId"],
                "scoutName": j["scoutName"],
                "regionIds": [],
                "players": 0,
            },
        )
        o["players"] += 1
        if j["scoutingRegionId"] and j["scoutingRegionId"] not in o["regionIds"]:
            o["regionIds"].append(j["scoutingRegionId"])

    return cast(
        dict[str, Any],
        {
            "scouts": sorted(ojeadores.values(), key=lambda o: -o["players"]),
            "players": jugadores,
        },
    )


@router.get(
    "/teams/{team_id}/academy/skill-scores",
    summary="Qué entrenar, con los parámetros que elija el usuario",
    dependencies=[Depends(require_team_owner)],
)
async def academy_skill_scores(
    team_id: int,
    soon_max_days: int = Query(
        yss.SOON_MAX_DAYS,
        ge=0,
        le=112,
        description="Los días del corte: sale joven quien lo hace con menos de 17;<este número>",
    ),
    weight_base: float = Query(
        yss.DEFAULT_WEIGHT_BASE,
        ge=yss.MIN_WEIGHT_BASE,
        le=yss.MAX_WEIGHT_BASE,
        description="Cuánto separa un peldaño del siguiente; 3 son los pesos originales",
    ),
    trainable_method: str = Query(
        yss.TrainableMethod.EDIT,
        description=(
            "De dónde sale el conteo de «entrenables»: attack / midfield / defence "
            "(aporte de la habilidad a ese bloque), senior (lo que entrena el primer "
            "equipo, 16 contra 0) o edit (a mano)"
        ),
    ),
    trainable_weight: float | None = Query(
        None,
        ge=0,
        le=100,
        description=(
            "Peso del bonus personalizado. Si no se manda, lo sugiere la escalera "
            "(el peldaño -2 de la base)"
        ),
    ),
    trainable: str = Query(
        "",
        description=(
            "Cuántos canteranos reciben cada entrenamiento, como «habilidad:n» separado por comas"
        ),
    ),
    fog_max: float = Query(
        m5.NIEBLA_MAXIMA,
        ge=0,
        le=1,
        description=(
            "Cuánta niebla se tolera en un puntaje antes de dejar de fiarse de él. "
            "0,5 = si más de la mitad del número es gente sin revelar, no vale como "
            "recomendación"
        ),
    ),
    min_to_double: int = Query(
        m5.MINIMO_PARA_DOBLAR,
        ge=1,
        le=16,
        description=(
            "Cuántos canteranos buenos hacen falta para que doblar la mejor habilidad "
            "tenga sentido. Con menos, la segunda dosis cae en desconocidos"
        ),
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Recalcula el ranking sin tocar el método.

    Los tres parámetros son opiniones, no hechos: dónde cae el corte del
    plazo, cuánto pesa un peldaño sobre el de abajo, y a cuántos les llega de
    verdad cada entrenamiento. El resto —la nota por habilidad, los cubos, la
    escalera— es la metodología y no se negocia desde la URL.
    """
    counts: dict[str, float] = {}
    for chunk in trainable.split(","):
        skill, _, raw = chunk.partition(":")
        skill = skill.strip()
        if skill not in yss.SKILLS:
            continue
        try:
            valor = float(raw)
        except ValueError:
            continue
        # Un negativo restaría puntaje, que no significa nada: nadie puede
        # recibir menos de cero entrenamientos.
        counts[skill] = max(0.0, min(valor, float(yss.SQUAD_NORMALISER)))

    if trainable_method not in set(yss.TrainableMethod):
        raise HTTPException(422, f"método de entrenables desconocido: {trainable_method}")
    service = AcademyQueryService(session)
    counts = await service.trainable_by_method(team_id, trainable_method, counts)

    rows = await service.skill_scores(
        team_id,
        soon_max_days=soon_max_days,
        weight_base=weight_base,
        trainable_weight=trainable_weight,
        trainable=counts,
    )
    if rows is None:
        raise HTTPException(404, f"team {team_id} sin canteranos")
    return cast(
        dict[str, Any],
        _camel(
            {
                "fogMax": fog_max,
                "minToDouble": min_to_double,
                "soonMaxDays": soon_max_days,
                "weightBase": weight_base,
                "trainableMethod": trainable_method,
                # Los pesos que salen de la base, para pintarlos sobre cada columna:
                # el usuario juega con potencias y quiere verlas, no deducirlas.
                "weights": yss.weights_for(weight_base),
                # El sugerido por la escalera y el que de verdad se usó: la pantalla
                # enseña el primero como propuesta y el segundo como valor del mando.
                "suggestedTrainableWeight": yss.trainable_weight_for(weight_base),
                # Las plazas que entrena cada cosa, para que «Editar a mano» arranque
                # de la verdad en vez de ceros: el usuario ajusta, no teclea de cero
                # unos numeros que la aplicacion ya sabe.
                "slotCounts": yss.slot_trainable(),
                "trainableWeight": (
                    yss.trainable_weight_for(weight_base)
                    if trainable_weight is None
                    else trainable_weight
                ),
                # La pareja sugerida: la habilidad que mas puntua y, de la segunda,
                # la FORMA que mas solapa con la primera. Sin eso, «Defensa + Pases»
                # se lee como una recomendacion util cuando en realidad no dejaria a
                # nadie recibiendo las dos cosas.
                "suggestion": _pareja_sugerida(
                    rows,
                    weight_base=weight_base,
                    niebla_maxima=fog_max,
                    minimo_para_doblar=min_to_double,
                ),
                # Todos los entrenamientos, variantes incluidas: son las opciones
                # reales de los dos selectores. Antes solo se ofrecian las siete
                # habilidades, asi que «Pases (defensas y centro del campo completo)»
                # no se podia elegir aunque la sugerencia la recomendara.
                "trainings": [
                    {"code": e.codigo, "label": e.label, "skill": e.skill}
                    for e in ENTRENAMIENTOS.values()
                ],
                "skillScores": [asdict(r) for r in rows],
            }
        ),
    )


@router.get(
    "/teams/{team_id}/academy/scouts-ledger",
    summary="La cuenta de cada ojeador: lo que cuesta y lo que ha traído",
    dependencies=[Depends(require_team_owner)],
)
async def academy_scouts_ledger(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Coste semanal contra lo que dejaron sus canteranos.

    Las cifras de dinero salen de la misma fuente que el ROI de la cantera,
    para que las dos pantallas no puedan discrepar sobre el mismo jugador.
    """
    from app.application.queries.ojeadores import OjeadoresQueryService

    return await OjeadoresQueryService(session).get(team_id)
