"""El rival de Promoción, que no está en tu clasificación.

2026-11-01, pedido del usuario: «agregar el rival de Promoción a la lista de
Rivales de Liga» y «también quiero el rival de Promoción, desde que se conoce
hasta que ya se haya jugado, en la flor del dashboard».
"""
import asyncio
from datetime import UTC, datetime, timedelta

from app.application.queries.flor_de_fuerza import sectores_del_rival_de_promocion
from app.application.queries.league import LeagueQueryService
from app.application.queries.promocion import rival_de_promocion
from app.domain.value_objects.ht_constants import (
    MATCH_TYPE_LEAGUE,
    MATCH_TYPE_QUALIFICATION,
)
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

CUANDO = datetime(2026, 11, 8, 21, 40, tzinfo=UTC)
EL_DE_ARRIBA = 712_345


async def _con_promocion(*, jugado: bool, rival: int = EL_DE_ARRIBA, en_casa: bool = True):
    factory, team_id = await seeded_session()
    async with factory() as s:
        team = await s.get(m.Team, team_id)
        assert team is not None
        team.series_ht_id = 34162
        s.add(
            m.Match(
                ht_match_id=773_000_001,
                played_at=CUANDO,
                match_type=MATCH_TYPE_QUALIFICATION,
                status="finished" if jugado else "UPCOMING",
                home_team_ht_id=HT_TEAM_ID if en_casa else rival,
                away_team_ht_id=rival if en_casa else HT_TEAM_ID,
                home_team_name="Pulgas Arrechas" if en_casa else "Los de Arriba",
                away_team_name="Los de Arriba" if en_casa else "Pulgas Arrechas",
                home_goals=2 if jugado else -1,
                away_goals=1 if jugado else -1,
            )
        )
        await s.commit()
    return factory, team_id


def _pide(factory, team_id, fn):
    async def go():
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            return await fn(s, team)

    return asyncio.run(go())


def test_el_rival_de_promocion_sale_con_su_sede() -> None:
    factory, team_id = asyncio.run(_con_promocion(jugado=False, en_casa=False))
    rival = _pide(factory, team_id, lambda s, t: rival_de_promocion(s, t))
    assert rival is not None
    assert (rival.ht_team_id, rival.nombre) == (EL_DE_ARRIBA, "Los de Arriba")
    # La sede es segura en promoción, y el motor la usa.
    assert rival.en_casa is False
    assert rival.pendiente is True


def test_una_vez_jugado_desaparece_de_los_dos_sitios() -> None:
    """La lista de Rivales y la flor tienen ya la MISMA ventana: mientras se
    sepa y hasta que se juegue.

    El 2026-11-01 la lista lo quería también después de jugado; el 2026-11-02
    el usuario lo quitó: «si ya jugué Promoción, no necesito verlo en esa
    lista». Un rival que ya no es rival ocupaba una fila.
    """
    factory, team_id = asyncio.run(_con_promocion(jugado=True))

    # El partido sigue en la base, y la consulta lo encuentra si se le pide
    # todo: lo que cambia es que nadie se lo pide así.
    rival = _pide(factory, team_id, lambda s, t: rival_de_promocion(s, t))
    assert rival is not None and rival.pendiente is False

    # Ni la lista de Rivales ni la flor lo enseñan.
    assert _pide(factory, team_id, lambda s, t: rival_de_promocion(s, t, solo_pendiente=True)) is None
    assert _pide(factory, team_id, lambda s, t: sectores_del_rival_de_promocion(s, t, set())) is None


def test_sin_promocion_no_hay_rival_y_no_es_un_error() -> None:
    """No jugar promoción es el caso normal: ni la juega todo el mundo ni todas
    las temporadas."""
    factory, team_id = asyncio.run(seeded_session())
    assert _pide(factory, team_id, lambda s, t: rival_de_promocion(s, t)) is None


def test_el_petalo_de_la_promocion_entra_mientras_este_pendiente() -> None:
    factory, team_id = asyncio.run(_con_promocion(jugado=False))
    fila = _pide(factory, team_id, lambda s, t: sectores_del_rival_de_promocion(s, t, set()))
    assert fila is not None
    assert fila.es_promocion is True
    assert fila.es_copa is False
    assert fila.nombre == "Los de Arriba"
    # Sin partidos suyos guardados el pétalo existe pero sin medias: la
    # pantalla ya sabe pintar eso, y es mejor que no enseñarlo.
    assert fila.partidos == 0


def test_si_el_rival_ya_esta_en_la_flor_no_se_repite() -> None:
    """Dos pétalos del mismo equipo lo contarían dos veces en la
    normalización, igual que con el de Copa."""
    factory, team_id = asyncio.run(_con_promocion(jugado=False))
    assert (
        _pide(factory, team_id, lambda s, t: sectores_del_rival_de_promocion(s, t, {EL_DE_ARRIBA}))
        is None
    )


def test_la_promocion_no_se_confunde_con_un_partido_de_liga() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            s.add(
                m.Match(
                    ht_match_id=773_000_009,
                    played_at=CUANDO - timedelta(days=7),
                    match_type=MATCH_TYPE_LEAGUE,
                    status="UPCOMING",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=600_001,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Rival de Liga",
                    home_goals=-1,
                    away_goals=-1,
                )
            )
            await s.commit()
        return factory, team_id

    factory, team_id = asyncio.run(go())
    assert _pide(factory, team_id, lambda s, t: rival_de_promocion(s, t)) is None


def test_la_respuesta_de_liga_lo_suelta_al_pitido() -> None:
    """Y la comprobación de verdad: lo que Liga manda a la pantalla.

    Es donde el usuario lo veía. Por jugar, viaja; jugado, no viaja, así que la
    lista de Rivales no tiene ni que filtrarlo.
    """

    async def respuesta(jugado: bool):
        factory, team_id = await _con_promocion(jugado=jugado)
        # Liga necesita una clasificación para responder: sin ella la consulta
        # devuelve `None` entera y no habría nada que mirar.
        async with factory() as s:
            sync = m.Sync(
                user_id=1, team_id=team_id, kind="manual", status="completed", started_at=CUANDO
            )
            s.add(sync)
            await s.flush()
            for i, (ht_id, nombre) in enumerate(
                [(HT_TEAM_ID, "Pulgas Arrechas"), (600_001, "Otro"), (600_002, "Un tercero")]
            ):
                s.add(
                    m.Standing(
                        sync_id=sync.id, series_ht_id=34162, season=84, match_round=2,
                        captured_at=CUANDO, team_ht_id=ht_id, team_name=nombre, position=i + 1,
                        played=2, won=2 - i, draws=0, lost=i,
                        goals_for=4 - i, goals_against=i, points=6 - i * 3,
                    )
                )
            await s.commit()
        async with factory() as s:
            r = await LeagueQueryService(s).get(team_id, runs=200)
        assert r is not None
        return r.promotion_rival

    por_jugar = asyncio.run(respuesta(False))
    assert por_jugar is not None
    assert por_jugar["name"] == "Los de Arriba"
    assert por_jugar["isHome"] is True  # `_con_promocion` lo pone en casa por defecto
    # `pending` ya no viaja: sería siempre True y no diría nada.
    assert "pending" not in por_jugar

    assert asyncio.run(respuesta(True)) is None
