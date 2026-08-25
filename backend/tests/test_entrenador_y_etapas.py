"""Dos finales de un expediente de comisiones, y de que etapa se cuentan.

Aportado por el usuario el 2026-08-25.
"""
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.domain.engines import ex_player_watch as vigilancia
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"


# ── Ser entrenador cierra el expediente ─────────────────────────────────────

def test_el_bloque_de_entrenador_basta() -> None:
    """Comprobado en vivo el 2026-08-25 contra los 24 jugadores del equipo:
    solo uno trae `TrainerData` --el entrenador, con nivel 5-- y la ficha
    individual de un jugador normal no lo trae en absoluto."""
    assert vigilancia.es_entrenador({"is_player_trainer": True}) is True
    assert vigilancia.es_entrenador({"is_player_trainer": False}) is False
    assert vigilancia.es_entrenador({}) is False
    assert vigilancia.es_entrenador(None) is False


def test_ser_entrenador_cierra_a_cualquiera_incluido_el_canterano() -> None:
    """Un entrenador ya no puede venderse, asi que no habra reventa jamas.

    Es lo que lo distingue de la reventa, que solo cierra al comprado.
    """
    for canterano in (True, False):
        assert vigilancia.motivo_de_cierre(
            canterano=canterano, revendido=False, desaparecido=False,
            salio_sin_comprador=False, entrenador=True,
        ) == "entrenador"


def test_desaparecer_manda_sobre_ser_entrenador() -> None:
    """Si su ficha ya no existe, eso es lo que hay que decir."""
    assert vigilancia.motivo_de_cierre(
        canterano=True, revendido=False, desaparecido=True,
        salio_sin_comprador=False, entrenador=True,
    ) == "despedido"


def test_sin_ser_entrenador_el_canterano_sigue_vigilado() -> None:
    """La regla vieja no se toca: un canterano no se cierra por revenderse."""
    assert vigilancia.motivo_de_cierre(
        canterano=True, revendido=True, desaparecido=False,
        salio_sin_comprador=False, entrenador=False,
    ) is None


def test_el_parser_marca_al_entrenador() -> None:
    """El fixture se refresco el 2026-08-25: traia un `TrainerData` con nivel
    0 en un jugador que, al pedir su ficha real, NO lo trae. El fichero de
    pruebas estaba caducado y hacia creer que la etiqueta no bastaba."""
    ficha = get_parser("playerdetails")((FIXTURES / "playerdetails.xml").read_bytes())
    assert ficha["is_player_trainer"] is False


# ── Los partidos se cuentan por etapa ───────────────────────────────────────

async def _con_dos_etapas() -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(equipo)
        await s.flush()
        jugador = m.Player(
            team_id=equipo.id, ht_player_id=999, first_name="Ida", last_name="Vuelta",
            purchased_at=datetime(2026, 6, 1), sold_at=datetime(2026, 8, 1),
            games_played_for_us=20,   # el numero VIEJO, de la primera etapa
        )
        s.add(jugador)
        await s.flush()
        s.add(m.PlayerStint(
            player_id=jugador.id, ht_player_id=999, team_id=equipo.id,
            arrived_at=datetime(2024, 1, 1), left_at=datetime(2024, 6, 1),
            sale_transfer_id=111, games_played_for_us=20,
        ))
        s.add(m.PlayerStint(
            player_id=jugador.id, ht_player_id=999, team_id=equipo.id,
            arrived_at=datetime(2026, 6, 1), left_at=datetime(2026, 8, 1),
            sale_transfer_id=222, games_played_for_us=3,
        ))
        await s.commit()
        return SqlAlchemyUnitOfWork(factory), jugador.id


def test_la_etapa_que_cuenta_es_la_de_la_venta_mas_reciente() -> None:
    """38 ex-jugadores del usuario tienen mas de una etapa, y ocho tienen
    TRES. Con el numero del jugador, a los tres pasos se les aplicaria el
    mismo conteo."""
    async def corre() -> None:
        uow, player_id = await _con_dos_etapas()
        async with uow:
            etapa = await uow.session.scalar(
                select(m.PlayerStint)
                .where(
                    m.PlayerStint.player_id == player_id,
                    m.PlayerStint.sale_transfer_id.is_not(None),
                )
                .order_by(m.PlayerStint.left_at.desc())
                .limit(1)
            )
            jugador = await uow.session.get(m.Player, player_id)
        assert etapa.games_played_for_us == 3, "la segunda vuelta, no la primera"
        assert jugador.games_played_for_us == 20, (
            "el numero del jugador sigue siendo el viejo: por eso no se usa"
        )

    asyncio.run(corre())


def test_el_modelo_guarda_el_conteo_en_la_etapa() -> None:
    """Los campos existen desde el 2026-08-22; lo que faltaba era usarlos."""
    columnas = {c.name for c in m.PlayerStint.__table__.columns}
    assert {"games_played_for_us", "games_computed_at"} <= columnas
