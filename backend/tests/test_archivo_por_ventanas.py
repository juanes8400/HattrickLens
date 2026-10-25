"""El archivo de partidos, pedido en ventanas (2026-09-14).

Medido contra Hattrick: con un rango largo, matchesarchive lo ignora sin avisar
y devuelve los últimos tres meses. Lo que se vigila:
  · ninguna consulta pide más de `MATCH_ARCHIVE_WINDOW`;
  · una respuesta con partidos fuera de la ventana pedida NO sella el historial;
  · un historial sellado con la regla vieja se relee entero una vez, sin
    duplicar lo que ya estaba.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.application.commands.sync_team import (
    HORIZONTE_DEL_ARCHIVO,
    MATCH_ARCHIVE_WINDOW,
    VERSION_DEL_ARCHIVO,
    SyncResult,
    SyncTeamHandler,
)
from app.infrastructure.db import models as m
from tests.test_sync_flow import _setup

PROPIO = 537758
FUNDADO = datetime(2023, 1, 1, tzinfo=UTC)
HOY = datetime(2024, 1, 1, tzinfo=UTC)


def _fecha(p: dict[str, Any], clave: str) -> datetime:
    return datetime.strptime(p[clave], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def _partido(match_id: int, cuando: datetime) -> dict[str, Any]:
    return {
        "ht_match_id": match_id,
        "match_date": cuando.strftime("%Y-%m-%d %H:%M:%S"),
        "match_type": 1,
        "home_team_id": PROPIO,
        "away_team_id": 1,
        "home_team_name": "Pulgas Arrechas",
        "away_team_name": "Rival",
        "home_goals": 1,
        "away_goals": 0,
    }


class ArchivoRespetuoso:
    """Un partido a mitad de cada ventana, siempre dentro del rango pedido."""

    def __init__(self) -> None:
        self.consultas: list[dict[str, Any]] = []

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        assert file == "matchesarchive"
        self.consultas.append(params)
        desde, hasta = _fecha(params, "FirstMatchDate"), _fecha(params, "LastMatchDate")
        medio = desde + (hasta - desde) / 2
        return {"matches": [_partido(int(medio.timestamp()) // 3600, medio)]}


async def _equipo(uow, team_id: int, **campos: Any) -> None:
    async with uow as u:
        team = await u.session.get(m.Team, team_id)
        team.founded_at = FUNDADO
        for k, v in campos.items():
            setattr(team, k, v)
        await u.commit()


def test_el_archivo_se_pide_en_ventanas_y_se_sella_con_la_version() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)
        chpp = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, chpp)
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(u, team_id, PROPIO, HOY, result, on_progress=None)
            await u.commit()

        assert len(chpp.consultas) >= 5  # un año en ventanas de 12 semanas
        for c in chpp.consultas:
            assert _fecha(c, "LastMatchDate") - _fecha(c, "FirstMatchDate") <= MATCH_ARCHIVE_WINDOW
        assert _fecha(chpp.consultas[0], "FirstMatchDate") == FUNDADO
        assert _fecha(chpp.consultas[-1], "LastMatchDate") == HOY
        assert result.rescued_matches == len(chpp.consultas)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.matches_history_complete is True
            assert team.matches_history_version == VERSION_DEL_ARCHIVO

    asyncio.run(run())


def test_si_hattrick_ignora_el_rango_no_se_sella() -> None:
    """La respuesta real con un rango largo: partidos recientes, sin error."""

    class ArchivoQueIgnoraElRango:
        async def fetch(self, file: str, version: str = "latest", **params: Any):
            return {"matches": [_partido(1, HOY + timedelta(days=200))]}

    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)
        handler = SyncTeamHandler(uow, ArchivoQueIgnoraElRango())
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(u, team_id, PROPIO, HOY, result, on_progress=None)
            await u.commit()

        assert result.status == "partial"
        assert any("ignoró el rango" in e for e in result.errors)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.matches_history_complete is False
            total = await u.session.scalar(select(func.count()).select_from(m.Match))
        assert total == 0

    asyncio.run(run())


def test_un_historial_sellado_con_la_regla_vieja_se_relee_entero_una_vez() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        # Sellado por la versión 1: completo, con la marca en HOY.
        await _equipo(
            uow,
            team_id,
            matches_history_complete=True,
            matches_history_synced_until=HOY,
            matches_history_version=1,
        )
        chpp = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, chpp)

        async with uow as u:
            await handler._sync_match_history(
                u, team_id, PROPIO, HOY, SyncResult(sync_id=1, status="completed"), None
            )
            await u.commit()
        primeras = len(chpp.consultas)
        assert _fecha(chpp.consultas[0], "FirstMatchDate") == FUNDADO  # desde la fundación
        async with uow as u:
            total = await u.session.scalar(select(func.count()).select_from(m.Match))

        # Ya con la versión nueva: sólo la cola, y nada duplicado.
        chpp.consultas.clear()
        async with uow as u:
            await handler._sync_match_history(
                u,
                team_id,
                PROPIO,
                HOY + timedelta(days=7),
                SyncResult(sync_id=2, status="completed"),
                None,
            )
            await u.commit()
        assert len(chpp.consultas) == 1 < primeras
        async with uow as u:
            despues = await u.session.scalar(select(func.count()).select_from(m.Match))
        assert despues == total + 1

    asyncio.run(run())


# ── Que un corte no tire lo descargado (2026-10-25) ──────────────────────────
#
# Reporte de un usuario: «it tries to download 2000+ old matches, and then
# interrupts». El cursor se escribia en la misma frase que la marca de
# completo, al final del barrido, asi que un corte a mitad no dejaba NADA y el
# intento siguiente volvia a empezar por la fundacion. Con dos mil partidos eso
# no termina nunca.


class ArchivoQueSeCorta(ArchivoRespetuoso):
    """Contesta bien unas cuantas ventanas y luego revienta, como un tiempo de
    espera agotado o un fallo de CHPP a mitad de la importacion."""

    def __init__(self, aguanta: int) -> None:
        super().__init__()
        self.aguanta = aguanta

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        if len(self.consultas) >= self.aguanta:
            self.consultas.append(params)
            raise RuntimeError("se corto la conexion")
        return await super().fetch(file, version, **params)


def test_un_corte_guarda_lo_descargado_y_no_sella() -> None:
    """Lo hecho se queda, y la marca de completo NO se pone.

    Las dos mitades importan: sin guardar, el corte tira el trabajo; sin dejar
    la marca sin poner, el historial quedaria sellado con agujeros dentro.
    """

    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)
        chpp = ArchivoQueSeCorta(aguanta=2)
        handler = SyncTeamHandler(uow, chpp)
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(u, team_id, PROPIO, HOY, result, on_progress=None)
            await u.commit()

        # El sync NO revienta: el resto sigue siendo util.
        assert result.status == "partial"
        assert result.rescued_matches == 2, "las dos ventanas buenas tienen que estar guardadas"

        async with uow as u:
            guardados = await u.session.scalar(select(func.count()).select_from(m.Match))
            assert guardados == 2
            team = await u.session.get(m.Team, team_id)
            # Sin sellar: es lo que hace que la proxima vez continue.
            assert team.matches_history_complete is False
            # Pero CON cursor y version: es lo que dice por donde iba.
            assert team.matches_history_synced_until is not None
            assert team.matches_history_version == VERSION_DEL_ARCHIVO

    asyncio.run(run())


def test_el_intento_siguiente_SIGUE_no_vuelve_a_empezar() -> None:
    """La prueba del reporte entero.

    Primero se corta; luego se reintenta. La segunda tanda no puede volver a
    pedir la fundacion, porque eso es el bucle infinito que describia el
    usuario.
    """

    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)

        corta = ArchivoQueSeCorta(aguanta=2)
        handler = SyncTeamHandler(uow, corta)
        async with uow as u:
            await handler._sync_match_history(
                u, team_id, PROPIO, HOY, SyncResult(sync_id=1, status="completed"), on_progress=None
            )
            await u.commit()
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            hasta_donde = team.matches_history_synced_until

        entero = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, entero)
        result = SyncResult(sync_id=2, status="completed")
        async with uow as u:
            await handler._sync_match_history(u, team_id, PROPIO, HOY, result, on_progress=None)
            await u.commit()

        primera = _fecha(entero.consultas[0], "FirstMatchDate")
        assert primera > FUNDADO, "volvio a empezar por la fundacion: es el fallo reportado"
        assert primera <= hasta_donde.replace(tzinfo=UTC), "se salto un trozo del historial"

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.matches_history_complete is True, "la segunda pasada tiene que terminarlo"

    asyncio.run(run())


def test_la_primera_importacion_no_se_remonta_mas_alla_del_horizonte() -> None:
    """Un club de los viejos no paga veinte anos el primer dia.

    25 temporadas, la cifra que propuso quien lo reporto. No es un borrado: lo
    anterior no se pide, pero nada de lo guardado se toca.
    """

    async def run() -> None:
        uow, _unused, team_id = await _setup()
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.founded_at = datetime(1998, 5, 1, tzinfo=UTC)
            await u.commit()

        chpp = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, chpp)
        async with uow as u:
            await handler._sync_match_history(
                u, team_id, PROPIO, HOY, SyncResult(sync_id=1, status="completed"), on_progress=None
            )
            await u.commit()

        primera = _fecha(chpp.consultas[0], "FirstMatchDate")
        assert primera == HOY - HORIZONTE_DEL_ARCHIVO
        assert primera.year > 1998, "se remonto a la fundacion pese al horizonte"


    asyncio.run(run())


def test_un_club_joven_empieza_en_su_fundacion_no_en_el_horizonte() -> None:
    # El horizonte es un TOPE, no un desplazamiento: quien lleva un ano jugando
    # no puede acabar pidiendo partidos anteriores a su propia fundacion.
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)  # fundado en 2023

        chpp = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, chpp)
        async with uow as u:
            await handler._sync_match_history(
                u, team_id, PROPIO, HOY, SyncResult(sync_id=1, status="completed"), on_progress=None
            )
            await u.commit()

        assert _fecha(chpp.consultas[0], "FirstMatchDate") == FUNDADO

    asyncio.run(run())
