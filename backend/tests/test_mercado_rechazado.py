"""Cuando Hattrick no deja mirar el mercado, eso es una alerta, no un error.

2026-11-01, pedido del usuario después de un reporte de sus usuarios: el fallo
del paso del mercado «que sea un aviso en alertas, no un motivo para mostrarlo
ahí». «Ahí» es el cartel de sincronización parcial, donde salía pegado a los
errores que sí le piden algo al manager --una alineación incompleta-- con el
mismo tono.
"""
import asyncio
from unittest.mock import patch

from app.application.commands.sync_team import SyncTeamHandler
from app.application.commands.sync_team.comun import SyncResult
from app.domain.engines import insights as ins
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.conftest import FakeCHPP, seeded_session

RECHAZO = "Invalid parameter specified (10) Additional Info: ageMin"


def test_el_fallo_del_mercado_no_viaja_al_cartel_de_sincronizacion() -> None:
    async def go():
        factory, team_id = await seeded_session()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
        result = SyncResult(sync_id=1, status="completed")
        async with SqlAlchemyUnitOfWork(factory) as uow:
            with patch(
                "app.application.commands.paso_del_mercado.correr_el_paso_del_mercado",
                side_effect=RuntimeError(RECHAZO),
            ):
                await handler._paso_del_mercado(uow, team_id, result, None)
        async with factory() as s:
            equipo = await s.get(m.Team, team_id)
            return result, equipo.market_error, equipo.market_error_at

    result, error, cuando = asyncio.run(go())
    # Nada en el cartel, y el sync sigue siendo completo.
    assert result.errors == []
    assert result.status == "completed"
    # Pero no se pierde: queda en el club, con su fecha, para que lo cuente Alertas.
    assert error is not None
    assert RECHAZO in error
    assert cuando is not None


def test_un_paso_que_sale_bien_borra_el_aviso_anterior() -> None:
    """Un aviso que sobrevive a su causa es peor que no avisar."""

    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            equipo = await s.get(m.Team, team_id)
            equipo.market_error = RECHAZO
            await s.commit()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
        result = SyncResult(sync_id=1, status="completed")

        class PasoVacio:
            se_busco = False
            resueltas = 0

        async with SqlAlchemyUnitOfWork(factory) as uow:
            with patch(
                "app.application.commands.paso_del_mercado.correr_el_paso_del_mercado",
                return_value=PasoVacio(),
            ):
                await handler._paso_del_mercado(uow, team_id, result, None)
        async with factory() as s:
            equipo = await s.get(m.Team, team_id)
            return equipo.market_error, equipo.market_error_at

    assert asyncio.run(go()) == (None, None)


def test_la_alerta_dice_lo_que_hattrick_contesto() -> None:
    avisos = ins.mercado_rechazado(RECHAZO)
    assert len(avisos) == 1
    aviso = avisos[0]
    assert aviso.key == "market.rechazado"
    assert aviso.severity is ins.Severity.INFO
    # El motivo entra en el detalle: es lo único que sirve para reportarlo.
    assert RECHAZO in aviso.detail
    # Y la acción no le pide nada al manager, porque no hay nada que pedirle.
    assert "nada que arreglar" in aviso.action


def test_sin_fallo_guardado_no_hay_alerta() -> None:
    assert ins.mercado_rechazado(None) == []
    assert ins.mercado_rechazado("") == []
