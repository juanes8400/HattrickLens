"""«¿Qué pasó en el último entrenamiento?» (2026-09-19, pedido del usuario).

Lo primero es saber CUÁNDO fue, y eso no se estima: Hattrick publica la hora
de la actualización semanal de cada liga, y para la cantera, la cita del
próximo partido de entrenamiento. Desde esas dos fechas se retrocede de siete
en siete hasta la última que ya pasó.

Lo que se fija aquí es justo eso, más la distinción que evita mentir con
datos: «no subió nadie» y «todavía no has sincronizado» son dos silencios
distintos y no se pueden enseñar igual.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.academy import AcademyQueryService
from app.application.queries.ultimo_entrenamiento import (
    UltimoEntrenamientoQueryService,
    momento_de_la_ultima,
)
from app.infrastructure.db import models as m

HOY = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
#: La cita semanal de esta liga, en el futuro respecto a HOY.
PROXIMO = datetime(2026, 9, 25, 4, 30, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


async def _base():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory()


def test_la_cita_del_futuro_se_retrocede_hasta_la_ultima_que_ya_paso() -> None:
    ultima = momento_de_la_ultima(PROXIMO, ahora=HOY)
    assert ultima == datetime(2026, 9, 18, 4, 30, tzinfo=UTC)


def test_una_cita_ya_pasada_se_deja_donde_esta() -> None:
    pasada = datetime(2026, 9, 18, 4, 30, tzinfo=UTC)
    assert momento_de_la_ultima(pasada, ahora=HOY) == pasada


def test_sin_hora_de_la_liga_no_se_inventa_ninguna() -> None:
    assert momento_de_la_ultima(None, ahora=HOY) is None


async def _equipo_con_mundo(sesion, cita: datetime | None = PROXIMO):
    equipo = m.Team(ht_team_id=1, name="Test FC", ht_league_id=19, currency_rate=1.0)
    sesion.add(equipo)
    await sesion.flush()
    sesion.add(
        m.WorldContext(
            ht_league_id=19,
            season=83,
            match_round=9,
            training_date=cita,
            refreshed_at=HOY,
        )
    )
    await sesion.commit()
    return equipo.id


def test_el_parte_dice_que_los_datos_no_llegan_hasta_el_entrenamiento() -> None:
    """El caso real de esta cuenta: la última sincronización es ANTERIOR al
    último entrenamiento, así que «no subió nadie» sería falso."""

    async def go():
        sesion = await _base()
        team_id = await _equipo_con_mundo(sesion)
        jugador = m.Player(ht_player_id=99, team_id=team_id, first_name="Ana", last_name="Prueba")
        sesion.add(jugador)
        await sesion.flush()
        sesion.add(
            m.PlayerSnapshot(
                sync_id=1,
                player_id=jugador.id,
                captured_at=HOY - timedelta(days=5),
                age_years=25,
                age_days=1,
                tsi=1000,
                form=5,
                stamina=7,
                experience=3,
                salary=1000,
                content_hash=b"x" * 32,
            )
        )
        await sesion.commit()
        return await UltimoEntrenamientoQueryService(sesion).get(team_id)

    parte = run(go())
    assert parte is not None
    assert parte.at == datetime(2026, 9, 18, 4, 30, tzinfo=UTC)
    assert parte.pending_sync is True
    assert parte.ups == []


def test_el_parte_trae_las_subidas_de_esa_semana_y_no_las_de_otra() -> None:
    async def go():
        sesion = await _base()
        team_id = await _equipo_con_mundo(sesion)
        jugador = m.Player(ht_player_id=99, team_id=team_id, first_name="Ana", last_name="Prueba")
        sesion.add(jugador)
        await sesion.flush()
        sesion.add(
            m.PlayerSnapshot(
                sync_id=1,
                player_id=jugador.id,
                # Después del entrenamiento: los datos sí lo cubren.
                captured_at=HOY,
                age_years=25,
                age_days=1,
                tsi=1000,
                form=5,
                stamina=7,
                experience=3,
                salary=1000,
                content_hash=b"x" * 32,
            )
        )
        # La semana del último entrenamiento es la 83-09 (el mundo dice que
        # HOY es 83-09 y el entrenamiento cae en la misma semana).
        sesion.add(
            m.SkillUp(
                team_id=team_id,
                ht_player_id=99,
                skill_id=7,  # pases
                old_level=6,
                new_level=7,
                season=83,
                match_round=9,
                day_number=3,
            )
        )
        sesion.add(
            m.SkillUp(
                team_id=team_id,
                ht_player_id=99,
                skill_id=7,
                old_level=5,
                new_level=6,
                season=83,
                match_round=8,
                day_number=3,
            )
        )
        await sesion.commit()
        return await UltimoEntrenamientoQueryService(sesion).get(team_id)

    parte = run(go())
    assert parte is not None
    assert parte.pending_sync is False
    assert [(u.name, u.skill, u.from_level, u.to_level) for u in parte.ups] == [
        ("Ana Prueba", "passing", 6, 7)
    ]
    assert parte.previous_ups == 1
    assert parte.season_week == "83-09"


def test_la_cantera_entrena_despues_de_su_partido() -> None:
    """El anclaje juvenil es otro: la cita del próximo partido de
    entrenamiento, no la actualización semanal del primer equipo."""

    async def go():
        sesion = await _base()
        equipo = m.Team(
            ht_team_id=1,
            name="Test FC",
            currency_rate=1.0,
            youth_next_training_match_at=datetime(2026, 9, 24, 21, 42, tzinfo=UTC),
        )
        sesion.add(equipo)
        await sesion.commit()
        svc = AcademyQueryService(sesion)
        return await svc._ultimo_entrenamiento_juvenil(equipo.id, now=HOY)

    assert run(go()) == datetime(2026, 9, 17, 21, 42, tzinfo=UTC)


def test_sin_la_cita_juvenil_no_se_estima_nada() -> None:
    async def go():
        sesion = await _base()
        equipo = m.Team(ht_team_id=1, name="Test FC", currency_rate=1.0)
        sesion.add(equipo)
        await sesion.commit()
        return await AcademyQueryService(sesion)._ultimo_entrenamiento_juvenil(equipo.id, now=HOY)

    assert run(go()) is None


def test_una_bajada_no_es_una_subida() -> None:
    """Hattrick reporta las dos cosas en el mismo sitio.

    Con datos reales de esta cuenta, tres de los cinco movimientos de la
    semana eran CAÍDAS de Resistencia y de Lateral. Contarlas como subidas
    convertía una mala semana en una buena noticia, así que el parte las
    separa y cada una sabe hacia dónde fue.
    """

    async def go():
        sesion = await _base()
        team_id = await _equipo_con_mundo(sesion)
        for ht_id, nombre in ((1, "Sube"), (2, "Baja")):
            jugador = m.Player(
                ht_player_id=ht_id, team_id=team_id, first_name=nombre, last_name="Prueba"
            )
            sesion.add(jugador)
        await sesion.flush()
        sesion.add(
            m.PlayerSnapshot(
                sync_id=1,
                player_id=1,
                captured_at=HOY,
                age_years=25,
                age_days=1,
                tsi=1000,
                form=5,
                stamina=7,
                experience=3,
                salary=1000,
                content_hash=b"x" * 32,
            )
        )
        sesion.add(
            m.SkillUp(
                team_id=team_id,
                ht_player_id=1,
                skill_id=7,
                old_level=6,
                new_level=7,
                season=83,
                match_round=9,
                day_number=3,
            )
        )
        # La Resistencia se cae sola cuando el entrenamiento va por otro lado.
        sesion.add(
            m.SkillUp(
                team_id=team_id,
                ht_player_id=2,
                skill_id=2,
                old_level=8,
                new_level=7,
                season=83,
                match_round=9,
                day_number=3,
            )
        )
        await sesion.commit()
        return await UltimoEntrenamientoQueryService(sesion).get(team_id)

    parte = run(go())
    assert parte is not None
    deltas = {u.name: u.delta for u in parte.ups}
    assert deltas == {"Sube Prueba": 1, "Baja Prueba": -1}
    # Y la que baja se llama por su nombre, no «stamina» en crudo.
    assert [u.skill_label for u in parte.ups if u.delta < 0] == ["Resistencia"]
    # Las subidas van primero.
    assert parte.ups[0].delta > 0
