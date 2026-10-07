"""Los eventos de entrenamiento.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from datetime import datetime

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    ProgressReporter,
    SyncResult,
    _nombre_legible,
    _report,
    _tras_fallo,
)
from app.domain.ports.repositories import UnitOfWork


class EntrenamientoMixin(BaseDeSync):
    """Los eventos de entrenamiento."""

    async def _sync_training_events(
        self,
        uow: UnitOfWork,
        team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Subidas confirmadas por Hattrick, jugador por jugador.

        CORRECCIÓN 2026-08-19: `trainingevents.xml` estaba en la lista de
        ficheros del sync general, y ahí se pedía SIN `playerID`. Hattrick
        responde a eso con error 56, así que la tabla `skill_ups` llevaba
        vacía desde siempre pese a tener parser, handler y modelo. El fichero
        solo existe por jugador, verificado en vivo: con `playerID` devuelve
        sus eventos con `Season` y `MatchRound`, que es justo el "83-03" que
        pide la columna "Última mejora".

        Es una llamada por jugador de la plantilla activa, igual que
        `playerdetails`. El guardado ya era idempotente: un mismo pop no se
        cuenta dos veces.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        jugadores = (
            (
                await uow.session.execute(
                    select(m.Player.ht_player_id).where(
                        m.Player.team_id == team_id, m.Player.left_team_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        if not jugadores:
            return
        await _report(on_progress, "Leyendo subidas confirmadas por Hattrick...")
        for ht_player_id in jugadores:
            try:
                payload = await self._chpp.fetch(
                    "trainingevents",
                    version=FILE_VERSIONS["trainingevents"],
                    playerID=ht_player_id,
                )
            except Exception as exc:  # noqa: BLE001 - un jugador no tumba el sync
                result.errors.append(f"{_nombre_legible('trainingevents')} ({ht_player_id}): {exc}")
                await _tras_fallo(uow, exc)
                continue
            await self._persist_skill_ups(uow, team_id, payload, captured_at, result)
