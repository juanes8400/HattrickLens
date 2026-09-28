"""«Cambios» enseña lo que movió ESTA sincronización, no lo de toda la semana.

2026-09-27, reporte del usuario: «Cambios trae un montón de cambios que no
correspondían al último delta; si al jugador X sólo le cambia fidelidad, me
muestras un montón de cosas».

Medido sobre sus propios datos antes de tocar nada: en la sincronización del
sábado 12 de septiembre la pantalla sacaba 58 filas cuando ese sync había
movido 3. La causa era que cada jugador se comparaba contra la última foto
anterior al LUNES de la semana en curso, así que todo lo que se movía el lunes
se volvía a contar el martes, el miércoles y hasta el domingo.

El corte semanal venía del primer día y defendía algo razonable --que
sincronizar dos veces seguidas no dejara un informe vacío-- pero eso se
resolvió de otra forma el 2026-08-24, cuando el informe pasó a ser el del
último sync y la pantalla aprendió a decir «Nada nuevo». Desde entonces las dos
reglas se contradecían: el aviso de arriba contaba 3 y la tabla de abajo
enseñaba cincuenta.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.sync_comparison import _player_report
from app.infrastructure.db import models as m

EQUIPO = 537758
#: Lunes, miércoles y sábado de la misma semana ISO.
LUNES = datetime(2026, 9, 7, 3, 0, tzinfo=UTC)
MIERCOLES = datetime(2026, 9, 9, 14, 0, tzinfo=UTC)
SABADO = datetime(2026, 9, 12, 15, 0, tzinfo=UTC)

BASE = {
    "age_years": 28,
    "age_days": 40,
    "tsi": 9000,
    "salary": 120_000,
    "form": 6,
    "stamina": 7,
    "experience": 5,
    "loyalty": 12,
    "leadership": 4,
    "keeper": 1,
    "defending": 10,
    "playmaking": 8,
    "winger": 5,
    "passing": 7,
    "scoring": 3,
    "set_pieces": 4,
    "injury_level": -1,
    "is_transfer_listed": False,
}


async def _base():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        equipo = m.Team(ht_team_id=EQUIPO, name="Pulgas Arrechas", currency_rate=10.0)
        s.add(equipo)
        await s.flush()
        jugador = m.Player(
            ht_player_id=111222,
            team_id=equipo.id,
            first_name="Jugador",
            last_name="X",
        )
        s.add(jugador)
        await s.flush()

        syncs: dict[str, int] = {}
        for nombre, cuando, cambios in (
            ("lunes", LUNES, {}),
            # El miercoles se le movieron tres cosas.
            ("miercoles", MIERCOLES, {"stamina": 8, "tsi": 9600, "playmaking": 9}),
            # Y el sabado SOLO la fidelidad.
            ("sabado", SABADO, {"stamina": 8, "tsi": 9600, "playmaking": 9, "loyalty": 13}),
        ):
            fila = m.Sync(
                user_id=1,
                team_id=equipo.id,
                kind="players",
                status="completed",
                started_at=cuando,
                finished_at=cuando,
            )
            s.add(fila)
            await s.flush()
            syncs[nombre] = fila.id
            valores = {**BASE, **cambios}
            s.add(
                m.PlayerSnapshot(
                    player_id=jugador.id,
                    sync_id=fila.id,
                    captured_at=cuando,
                    # La huella que usa el sync para no reescribir una foto
                    # identica. Aqui solo tiene que ser distinta por foto.
                    content_hash=str(sorted(valores.items())).encode("utf-8"),
                    **valores,
                )
            )
        await s.commit()
        return factory, equipo.id, syncs


def _informe(nombre: str):
    async def run():
        factory, team_id, syncs = await _base()
        async with factory() as s:
            filas, _ = await _player_report(s, team_id, syncs[nombre], 10.0, "US$")
        return filas

    return asyncio.run(run())


def test_solo_sale_lo_que_movio_esta_sincronizacion() -> None:
    """El caso literal del usuario: el sábado sólo cambió la fidelidad."""
    filas = _informe("sabado")
    assert len(filas) == 1
    etiquetas = [c["label"] for c in filas[0]["changes"]]
    assert etiquetas == ["Fidelidad"], etiquetas
    # Y el TSI, que se movió el miércoles, tampoco se vuelve a contar.
    assert filas[0]["tsiDelta"] == 0


def test_lo_del_miercoles_sale_el_miercoles() -> None:
    """No se pierde nada: cada cambio se cuenta una vez, el día que pasó."""
    filas = _informe("miercoles")
    assert len(filas) == 1
    etiquetas = sorted(c["label"] for c in filas[0]["changes"])
    assert etiquetas == ["Jugadas", "Resistencia"], etiquetas
    assert filas[0]["tsiDelta"] == 600


def test_la_primera_lectura_de_un_jugador_es_un_alta() -> None:
    """Sin foto anterior no hay delta que calcular, y no se inventa uno."""
    filas = _informe("lunes")
    assert len(filas) == 1
    assert filas[0]["isNew"] is True
    assert filas[0]["tsiDelta"] is None
