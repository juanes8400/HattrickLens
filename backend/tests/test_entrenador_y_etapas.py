"""Dos finales de un expediente de comisiones, y de que etapa se cuentan.

Aportado por el usuario el 2026-08-25.
"""
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    """Lo que decide es `is_player_trainer`; de donde sale, mas abajo."""
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


def test_un_jugador_normal_TRAE_la_etiqueta_vacia() -> None:
    """El fallo que cerro 121 expedientes, 2026-08-25.

    En `playerdetails.xml` v3.2 TODO jugador trae `<TrainerData />` vacio, asi
    que dar por entrenador a quien tuviera la etiqueta cerraba la vigilancia
    de comisiones de cualquiera al que se le pidiera la ficha.

    La regla vieja se comprobo contra `players.xml` --donde solo el entrenador
    trae el bloque-- y se aplico a `playerdetails.xml`, que es otro fichero.
    Los dos recortes de aqui son reales.
    """
    ficha = get_parser("playerdetails")(
        (FIXTURES / "playerdetails_no_entrenador.xml").read_bytes()
    )
    assert ficha["is_player_trainer"] is False, (
        "la etiqueta esta, pero vacia: no es el entrenador"
    )


def test_el_entrenador_trae_el_bloque_CON_contenido() -> None:
    """Asi viene el entrenador de verdad: con tipo y nivel dentro."""
    ficha = get_parser("playerdetails")(
        (FIXTURES / "playerdetails_entrenador.xml").read_bytes()
    )
    assert ficha["is_player_trainer"] is True


def test_el_parser_marca_al_entrenador() -> None:
    """El fixture general del equipo: ese jugador no es entrenador."""
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


# ── No cerrar en falso a quien acaba de irse ────────────────────────────────

def test_quien_acaba_de_irse_no_se_cierra_como_sin_comprador() -> None:
    """El caso Enyo Kasaliyski, 2026-08-25: vendido por 4.880.000 y cerrado
    como "se fue sin que nadie lo comprara" porque el libro todavia no
    reflejaba la venta. Su comision no se habria vigilado jamas."""
    assert vigilancia.motivo_de_cierre(
        canterano=False, revendido=False, desaparecido=False,
        salio_sin_comprador=True, recien_salido=True,
    ) is None


def test_quien_se_fue_hace_meses_si_se_cierra() -> None:
    """Ahi ya no hay venta en camino que esperar."""
    assert vigilancia.motivo_de_cierre(
        canterano=False, revendido=False, desaparecido=False,
        salio_sin_comprador=True, recien_salido=False,
    ) == "sin_comprador"


def test_el_plazo_de_gracia_se_mide_en_dias() -> None:
    ahora = datetime(2026, 8, 25, 12, 0)
    assert vigilancia.salio_hace_poco(datetime(2026, 8, 24, 23, 0), ahora) is True
    assert vigilancia.salio_hace_poco(datetime(2026, 8, 1), ahora) is False
    assert vigilancia.salio_hace_poco(None, ahora) is False


def test_desaparecer_manda_aunque_acabe_de_irse() -> None:
    """Si su ficha ya no existe, no hay venta que esperar."""
    assert vigilancia.motivo_de_cierre(
        canterano=False, revendido=False, desaparecido=True,
        salio_sin_comprador=True, recien_salido=True,
    ) == "despedido"


def test_la_reparacion_reabre_a_quien_si_tenia_venta() -> None:
    """Se cura sola, sin migracion: si hay venta, el motivo era falso."""
    async def corre() -> None:
        from app.application.commands.sync_team import SyncTeamHandler

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
            s.add(m.Player(
                team_id=equipo.id, ht_player_id=1, first_name="Con", last_name="Venta",
                sold_at=datetime(2026, 8, 24), sale_price=4_880_000,
                left_team_at=datetime(2026, 8, 24),
                resale_closed=True, resale_closed_reason="sin_comprador",
                previous_club_bonus_checked_at=datetime(2026, 8, 24),
            ))
            s.add(m.Player(
                team_id=equipo.id, ht_player_id=2, first_name="Sin", last_name="Venta",
                left_team_at=datetime(2026, 1, 1),
                resale_closed=True, resale_closed_reason="sin_comprador",
            ))
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        async with uow:
            n = await SyncTeamHandler(uow, None)._reabrir_cierres_por_error(uow, team_id)
            await uow.commit()
        assert n == 1

        async with uow:
            con = await uow.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 1))
            sin = await uow.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 2))
        assert con.resale_closed is False
        assert con.resale_closed_reason is None
        assert con.previous_club_bonus_checked_at is None, "hay que volver a mirarlo"
        assert sin.resale_closed is True, "ese si se fue sin comprador"

    asyncio.run(corre())


# ── El aviso de los cierres ─────────────────────────────────────────────────

def test_los_cierres_se_anuncian_todos_juntos() -> None:
    """2026-08-25, pedido asi: en "Cambios", TODOS JUNTOS.

    Un barrido completo cierra decenas --113 revendidos, 87 despedidos y 41
    sin comprador en la cuenta real-- y anunciarlos uno a uno enterraria bajo
    doscientas lineas lo que si importa: una comision de verdad.
    """
    from app.domain.engines.sync_diff import diff_expedientes_cerrados

    c = diff_expedientes_cerrados(
        {"despedido": 2, "entrenador": 1, "revendido": 1, "sin_comprador": 1}
    )
    assert c is not None
    assert c.after == 5
    assert c.summary == (
        "5 expedientes cerrados: 2 despedidos, 1 entrenador, 1 revendido, "
        "1 sin comprador"
    )


def test_un_solo_cierre_se_dice_en_singular() -> None:
    from app.domain.engines.sync_diff import diff_expedientes_cerrados

    c = diff_expedientes_cerrados({"entrenador": 1})
    assert c.summary == "1 expediente cerrado: 1 entrenador"


def test_sin_cierres_no_se_anuncia_nada() -> None:
    """La mayoria de las pulsaciones no cierran ninguno: una linea diciendo
    "0 expedientes cerrados" seria ruido en cada visita."""
    from app.domain.engines.sync_diff import diff_expedientes_cerrados

    assert diff_expedientes_cerrados({}) is None


# ── Una etapa sin fecha de llegada no puede costar la comision ───────────────

def test_una_etapa_sin_fecha_de_llegada_no_pierde_la_comision() -> None:
    """2026-08-25. El cambio a contar POR ETAPA metio un `return False`
    cuando la etapa no traia `arrived_at`, y eso perdia el importe entero.

    En la cuenta real fueron 17 ex-jugadores y 3,4 millones: Ramiro Pineda
    (1.050.000) y Ciro Moyano (900.000) entre ellos. Los dos tienen DOS
    etapas y la que cuenta llego con `arrived_at` en nulo.

    Se descubrio comparando el volcado de comisiones de antes de reabrirlo
    todo con lo que el barrido volvio a encontrar: faltaban 19.
    """
    async def corre() -> None:
        from app.application.commands.sync_team import SyncTeamHandler

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
                team_id=equipo.id, ht_player_id=463690984,
                first_name="Ramiro", last_name="Pineda",
                purchased_at=datetime(2021, 11, 28), sold_at=datetime(2022, 1, 29),
                games_played_for_us=10,
            )
            s.add(jugador)
            await s.flush()
            # Dos etapas, y la que cuenta SIN fecha de llegada: tal cual esta
            # en la base del usuario.
            s.add(m.PlayerStint(
                player_id=jugador.id, ht_player_id=463690984, team_id=equipo.id,
                arrived_at=datetime(2021, 11, 28), left_at=datetime(2021, 11, 28),
                sale_transfer_id=352945715,
            ))
            s.add(m.PlayerStint(
                player_id=jugador.id, ht_player_id=463690984, team_id=equipo.id,
                arrived_at=None, left_at=datetime(2022, 1, 29),
                sale_transfer_id=354241388,
            ))
            await s.commit()
            team_id = equipo.id

        class CHPPConReventa:
            """El historial real de Pineda: se lo vendimos al 19343 y este lo
            revendio por 35.000.000."""

            async def fetch(self, file: str, version: str = "latest", **_p: Any) -> dict:
                return {"transfers": [
                    {"ht_transfer_id": 3, "deadline": "2023-08-29 12:00:00",
                     "seller_team_id": 19343, "buyer_team_id": 775871,
                     "price": 35_000_000},
                    {"ht_transfer_id": 2, "deadline": "2022-01-29 14:55:00",
                     "seller_team_id": 537758, "buyer_team_id": 19343,
                     "price": 7_100_000},
                ]}

        uow = SqlAlchemyUnitOfWork(factory)
        async with uow:
            escribio = await SyncTeamHandler(uow, CHPPConReventa())._check_previous_club_bonus(
                uow, team_id, 463690984,
            )
            await uow.commit()

        assert escribio is True, "la comision no puede perderse por una fecha en nulo"
        async with uow:
            bono = await uow.session.scalar(
                select(m.PreviousClubBonus).where(
                    m.PreviousClubBonus.ht_player_id == 463690984
                )
            )
        assert bono.resale_price == 35_000_000
        assert bono.games_played_with_us == 10, "cae al numero del jugador"
        assert bono.amount == 1_050_000, "el 3% de la reventa, como estaba antes"

    asyncio.run(corre())
