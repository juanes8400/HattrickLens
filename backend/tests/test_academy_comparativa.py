"""Qué se movió en la academia, y contra qué se compara.

2026-09-04, pedido del usuario: que el puntaje de «qué entrenar» no sea una
cifra quieta, sino que diga cuánto se movió y por qué. La ventana la elige él
con un selector --último cambio, 1, 2 u 8 semanas-- y manda sobre TODO lo que
se compara: dos ventanas dentro de la misma pantalla es lo que hace imposible
explicar de dónde sale un número.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.academy import AcademyQueryService
from app.infrastructure.db import models as m


def run(coro):
    return asyncio.run(coro)


async def _academia(sesion, team_id: int, fotos):
    """Crea un canterano por entrada y sus fotos en el tiempo.

    `fotos` es {nombre: [(cuándo, winger, winger_max), ...]}, que es lo justo
    para mover un puntaje: la habilidad y su techo.
    """
    for i, (nombre, tomas) in enumerate(fotos.items(), start=1):
        jugador = m.YouthPlayer(
            ht_youth_player_id=1000 + i,
            team_id=team_id,
            first_name=nombre,
            last_name="Prueba",
        )
        sesion.add(jugador)
        await sesion.flush()
        for j, (cuando, nivel, techo) in enumerate(tomas):
            sesion.add(
                m.YouthSnapshot(
                    sync_id=1,
                    youth_player_id=jugador.id,
                    captured_at=cuando,
                    age_years=16,
                    age_days=10,
                    winger=nivel,
                    winger_max=techo,
                    content_hash=bytes([i, j]) * 16,
                )
            )
    await sesion.commit()


async def _montar(fotos):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    sesion = factory()
    equipo = m.Team(ht_team_id=1, name="Test FC", currency_rate=1.0)
    sesion.add(equipo)
    await sesion.commit()
    await _academia(sesion, equipo.id, fotos)
    return AcademyQueryService(sesion), equipo.id


HOY = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_el_techo_recien_revelado_se_marca() -> None:
    """No mueve el nivel pero sí el puntaje.

    Sin marcarlo, la cifra de «qué entrenar» subía y no había en la pantalla
    ni una flecha que lo explicara. Va en negrilla en la tabla.
    """

    async def go():
        svc, team_id = await _montar(
            {"Ireneo": [(HOY - timedelta(days=10), 4, None), (HOY, 4, 7)]}
        )
        return await svc.comparativa(team_id, "cambio")

    d = run(go())
    assert d is not None
    habilidad = d["players"][0]["skills"]["winger"]
    assert habilidad["maxNewlyKnown"] is True
    assert habilidad["before"] is None  # el nivel no se movió
    assert d["summary"]["ceilingsRevealed"] == 1
    assert d["summary"]["skillsUp"] == 0


def test_una_subida_de_nivel_recuerda_de_donde_venia() -> None:
    """El «4 ▲ 5 / 7» que pidió el usuario necesita el 4."""

    async def go():
        svc, team_id = await _montar({"Ireneo": [(HOY - timedelta(days=10), 4, 7), (HOY, 5, 7)]})
        return await svc.comparativa(team_id, "cambio")

    d = run(go())
    assert d is not None
    habilidad = d["players"][0]["skills"]["winger"]
    assert habilidad["before"] == 4
    assert habilidad["current"] == 5
    assert d["summary"]["skillsUp"] == 1


def test_la_ventana_decide_cuanto_se_ve() -> None:
    """«Hace N semanas» es el ESTADO de entonces, no los cambios de entonces.

    La subida ocurrió hace diez días. A una semana el nivel ya era 5, así que
    no hay nada que enseñar; a dos semanas todavía era 4 y la subida aparece.
    Esa es la razón de que el selector exista.
    """

    async def go():
        svc, team_id = await _montar(
            {
                "Ireneo": [
                    (HOY - timedelta(days=20), 4, 7),
                    (HOY - timedelta(days=10), 5, 7),
                    (HOY, 5, 7),
                ]
            }
        )
        return (
            await svc.comparativa(team_id, "1"),
            await svc.comparativa(team_id, "2"),
        )

    una, dos = run(go())
    assert una is not None and dos is not None
    assert una["players"][0]["skills"]["winger"]["before"] is None
    assert dos["players"][0]["skills"]["winger"]["before"] == 4


def test_sin_historico_tan_atras_no_se_inventan_llegadas() -> None:
    """Fallo real encontrado al probarlo (2026-09-04).

    Con la ventana en 8 semanas y tres semanas de datos, ningún canterano
    tenía foto vieja y los dieciocho salían marcados como recién llegados.
    Sin base con la que comparar, no se compara nada.
    """

    async def go():
        svc, team_id = await _montar({"Ireneo": [(HOY, 4, 7)], "Aitor": [(HOY, 3, None)]})
        return await svc.comparativa(team_id, "8")

    d = run(go())
    assert d is not None
    assert d["hasBaseline"] is False
    assert d["summary"]["arrivals"] == 0
    assert all(j["isNew"] is False for j in d["players"])
    assert all(x["delta"] is None for x in d["scores"])
