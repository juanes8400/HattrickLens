"""El proceso entero sobre UN jugador, de la regla de Hattrick hasta el precio.

Cinco etapas, que son las mismas que recorre el producto:

  1. quien es segun Hattrick    tipo, plantilla, exclusiones, rareza, dial
  2. que buscaria el juego      sus criterios, con las palabras de la escala
  3. nuestra terna y el plan    los cinco escalones y la peticion CHPP literal
  4. que tiene el fondo         los comparables que le sirven, y el precio
  5. a quien le serviria el     si fuera una venta, contra tu plantilla

Se ejecuta desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/el_proceso.py         EDAD DIAS  por def jug lat pas ano bp

Ejemplo (Labrana, el del 2026-10-19):

    ... el_proceso.py 24 14  1 11 4 5 5 3 7
"""
import asyncio, os, sqlite3, sys
from datetime import UTC, datetime
from pathlib import Path

# SE TRABAJA DESDE `backend/`, no desde la raiz como las demas herramientas de
# esta carpeta: `app.core.config` lee su `.env` del directorio actual y sin el
# no arranca. Asi tambien vale `dev.db` a secas.
os.chdir(Path(__file__).resolve().parents[3] / "backend")
sys.path.insert(0, ".")
from sqlalchemy import select

from app.application.commands.mercado_comparable import a_guardado
from app.domain.engines.criterios_hattrick import (
    criterios_de, rareza, es_holgado, _tipo, PLANTILLAS, EXCLUIDAS,
)
from app.domain.engines.mercado_comparable import (
    objetivo_de, terna, peso_de, lo_ensenaria_hattrick, plan_de_busqueda,
    comparables_de, estimar, OBJETIVO, Candidato,
)
from app.infrastructure.chpp.mercado import peticiones_de
from app.infrastructure.db import models as m
from app.infrastructure.db.session import SessionLocal

ESCALA = ["nulo","desastroso","horrible","pobre","débil","insuficiente","aceptable",
          "bueno","excelente","formidable","destacado","brillante","magnífico",
          "clase mundial","sobrenatural","titánico","extraterrestre","mítico",
          "mágico","utópico","divino"]
def pal(n): return ESCALA[n] if 0 <= n < len(ESCALA) else f"divino (+{n-20})"
H8 = ("keeper","defending","playmaking","winger","passing","scoring","set_pieces","stamina")

async def main():
    a = sys.argv[1:]
    if len(a) < 9:
        print(__doc__)
        return
    edad, dias = int(a[0]), int(a[1])
    N = dict(zip(("keeper","defending","playmaking","winger","passing","scoring","set_pieces"),
                 map(int, a[2:9])))
    N["stamina"] = 0

    print("=" * 74)
    print(f"  EDAD {edad} años {dias} días")
    for k in ("keeper","defending","playmaking","winger","passing","scoring","set_pieces"):
        print(f"    {k:11} {N[k]:2}  {pal(N[k])}")

    tipo = _tipo(N)
    print("\n" + "=" * 74)
    print("  1. QUIÉN ES, SEGÚN HATTRICK")
    print(f"    tipo: {tipo}  | plantilla: {', '.join(PLANTILLAS[tipo])}")
    print(f"    nunca pueden ser criterio: {', '.join(sorted(EXCLUIDAS[tipo]))}")
    print(f"    rareza {rareza(N)}  ->  dial {'HOLGADO' if es_holgado(N, edad=edad) else 'AJUSTADO'}")

    cr = criterios_de(edad, N)
    print("\n" + "=" * 74)
    print("  2. LO QUE HATTRICK BUSCARÍA")
    print(f"    Edad {cr.edad_minima}–{cr.edad_maxima}" +
          (f"   ·   Días <= {cr.tope_de_dias}" if cr.tope_de_dias else ""))
    for i, k in enumerate(cr.habilidades):
        marca = "criterio" if k.operador in ("=", "banda", ">=") else "tope"
        print(f"    {i+1}. {k.habilidad:11} {k.operador:5} {k.minimo:2}..{k.maximo:2}"
              f"   {pal(k.minimo)}–{pal(k.maximo)}   [{marca}]")

    o = objetivo_de(490889449, edad, N, especialidad=0)
    if o is None:
        print("\n  (sin terna: todas las habilidades a cero)"); return
    print("\n" + "=" * 74)
    print("  3. NUESTRA TERNA Y EL PLAN")
    print(f"    terna: {', '.join(f'{r.habilidad} {r.nivel}' for r in (o.primaria,o.secundaria,o.terciaria))}")
    for v in plan_de_busqueda(o):
        fr = " · ".join(f"{f.habilidad} {f.minimo}-{f.maximo}" for f in (v.primaria,v.secundaria,v.terciaria))
        print(f"    peso {v.peso:3}  edad {v.edad_minima}-{v.edad_maxima}   {fr}")
    print("\n    petición CHPP del escalón de Hattrick:")
    print(f"      {peticiones_de(plan_de_busqueda(o)[0])[0]}")

    c = sqlite3.connect("dev.db"); c.row_factory = sqlite3.Row
    async with SessionLocal() as s:
        fondo = [a_guardado(f) for f in (await s.execute(select(m.MarketSale))).scalars()]
    ahora = datetime.now(UTC)
    els = comparables_de(fondo, o, ahora)
    est = estimar(els)
    print("\n" + "=" * 74)
    print("  4. QUÉ TIENE EL FONDO PARA ÉL")
    print(f"    fondo del equipo: {len(fondo)} ventas  ->  le sirven {len(els)}")
    for x in els:
        print(f"      {x.peso:3}%  {'HT' if x.avalado_por_hattrick else '--'}  "
              f"{'cerrada' if x.venta.firme else 'puja   '}  {x.venta.precio//10:>12,} US$  {x.venta.nombre}")
    print(f"\n    cuentan para el número: {est.n}   hacen falta {OBJETIVO}")
    if est.media is None:
        print(f"    => SIN PRECIO. Faltan {OBJETIVO - est.n}.")
    else:
        print(f"    => media {est.media//10:,} US$   mediana {est.mediana//10:,} US$")

    print("\n" + "=" * 74)
    print("  5. SI ÉL FUERA UNA VENTA, ¿A QUIÉN DE LOS TUYOS LE SERVIRÍA?")
    t = terna(N)
    cand = Candidato(ht_player_id=490889449, nombre="candidato", edad=edad, dias=dias,
                     puja=1, precio_pedido=0, tiene_puja=True, plazo="", tsi=0,
                     especialidad=0, lesion=-1, vendedor=0, liga_del_vendedor=0, pais=0,
                     habilidades=dict(N), primaria=t[0], secundaria=t[1], terciaria=t[2])
    hubo = False
    for j in c.execute("""select id, ht_player_id, last_name from players
                          where team_id=1 and left_team_at is null and sale_price is null"""):
        f = c.execute("select * from player_snapshots where player_id=? order by captured_at desc limit 1", (j["id"],)).fetchone()
        if f is None: continue
        f = dict(f)
        oo = objetivo_de(j["ht_player_id"], f["age_years"] or 0, {h: f.get(h) or 0 for h in H8},
                         especialidad=f.get("specialty") or 0)
        if oo is None: continue
        p = peso_de(cand, oo)
        if p is not None:
            hubo = True
            print(f"      {p:3}%  {'avalado por Hattrick' if lo_ensenaria_hattrick(cand, oo) else 'sólo escalera nuestra':22}  {j['last_name']}")
    if not hubo:
        print("      a nadie.")
    print("=" * 74)

asyncio.run(main())
