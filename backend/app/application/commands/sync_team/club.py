"""El club y su cuerpo tecnico.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

import json
from datetime import UTC, datetime
from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    SyncResult,
    _parse_dt,
    dict_hash,
)
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_time import ht_to_utc


class ClubMixin(BaseDeSync):
    """El club y su cuerpo tecnico."""

    async def _persist_world(
        self,
        uow: UnitOfWork,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """worlddetails.xml, 2026-08-04, trae TODOS los países en
        `<LeagueList>`, no uno: se guarda una fila de `WorldContext` (+ sus
        `WorldCup`) por cada país, y se refresca `Team.currency_rate`/
        `currency_name` para el país del EQUIPO propio (cruzando por
        `Team.ht_league_id`, de teamdetails.xml), antes esos dos campos no
        los ponía nada en el flujo real, solo un script de desarrollo los
        había escrito a mano una vez."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)

        for league in payload.get("leagues", []):
            lid = league.get("ht_league_id", 0)
            row = await uow.session.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == lid)
            )
            if row is None:
                row = m.WorldContext(ht_league_id=lid)
                uow.session.add(row)
            row.country_id = league.get("country_id", 0)
            row.country_code = league.get("country_code", "")
            row.league_name = league.get("league_name", "")
            row.country_name = league.get("country_name", "")
            row.national_team_id = league.get("national_team_id", 0)
            row.u21_team_id = league.get("u21_team_id", 0)
            row.season = league.get("season", 0)
            row.season_offset = league.get("season_offset", 0)
            row.match_round = league.get("match_round", 0)
            row.match_rounds_left = league.get("match_rounds_left", 0)
            row.number_of_levels = league.get("number_of_levels", 0)
            row.league_system_id = league.get("league_system_id", 1)
            row.currency_name = league.get("currency_name", "")
            row.currency_rate = league.get("currency_rate", 1.0)
            # `campo` y no `field`: asi se llamaba, y tapaba el `field` que
            # este modulo importa de `dataclasses`.
            for campo, key in (
                ("training_date", "training_date"),
                ("economy_date", "economy_date"),
                ("cup_match_date", "cup_match_date"),
                ("series_match_date", "series_match_date"),
            ):
                raw = league.get(key) or ""
                try:
                    parsed = ht_to_utc(raw)
                except ValueError:
                    parsed = None
                setattr(row, campo, parsed)
            row.refreshed_at = captured_at
            result.snapshots_written += 1

            for cup in league.get("cups", []):
                cup_row = await uow.session.scalar(
                    select(m.WorldCup).where(
                        m.WorldCup.ht_league_id == lid,
                        m.WorldCup.cup_league_level == cup.get("cup_league_level", 0),
                        m.WorldCup.cup_level == cup.get("cup_level", 0),
                        m.WorldCup.cup_level_index == cup.get("cup_level_index", 0),
                    )
                )
                if cup_row is None:
                    cup_row = m.WorldCup(
                        ht_league_id=lid,
                        cup_level=cup.get("cup_level", 0),
                        cup_level_index=cup.get("cup_level_index", 0),
                    )
                    uow.session.add(cup_row)
                cup_row.ht_cup_id = cup.get("ht_cup_id", 0)
                cup_row.cup_name = cup.get("cup_name", "")
                cup_row.cup_league_level = cup.get("cup_league_level", 0)
                cup_row.match_round = cup.get("match_round", -1)
                cup_row.match_rounds_left = cup.get("match_rounds_left", 0)

            if team is not None and team.ht_league_id == lid:
                team.currency_name = row.currency_name
                team.currency_rate = row.currency_rate

    async def _persist_teamdetails(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        payload: dict[str, Any],
        result: SyncResult,
    ) -> None:
        """Nombre, liga y serie del equipo, y sobre todo `series_ht_id`
        (LeagueLevelUnitID), sin el cual no se puede pedir leaguedetails: ese
        fichero se sincroniza por serie, no por equipo."""
        team = next(
            (t for t in payload.get("teams", []) if t.get("ht_team_id") == ht_team_id),
            None,
        )
        if team is None:
            return
        from app.infrastructure.db import models as m

        row = await uow.session.get(m.Team, team_id)
        if row is None:
            return
        before = (
            row.name,
            row.league_name,
            row.series_name,
            row.series_ht_id,
            row.ht_league_id,
            row.ht_youth_team_id,
            row.still_in_cup,
            row.current_cup_id,
            row.current_cup_match_round,
            row.current_cup_match_rounds_left,
        )
        founded_changed = False
        row.name = team.get("name") or row.name
        if team.get("is_primary_club") is not None:
            row.is_primary_club = bool(team["is_primary_club"])
        row.league_name = team.get("league_name") or row.league_name
        row.series_name = team.get("series_name") or row.series_name
        row.series_ht_id = team.get("series_ht_id") or row.series_ht_id
        row.ht_league_id = team.get("ht_league_id") or row.ht_league_id
        # La cantera de ESTE club. Se guarda tambien el 0: "este club no tiene
        # academia" es un dato, y es el que evita pedirla y recibir la del
        # club principal. `None` = el fichero no lo trajo, no se toca nada.
        cantera = team.get("ht_youth_team_id")
        if cantera is not None:
            row.ht_youth_team_id = cantera
            if cantera:
                row.youth_team_name = team.get("youth_team_name") or row.youth_team_name
            else:
                row.youth_team_name = None
                row.youth_academy_created_at = None
        founded_at = _parse_dt(team.get("founded_at"))
        if founded_at is not None:
            current_founded = row.founded_at
            current_naive = (
                current_founded.astimezone(UTC).replace(tzinfo=None)
                if current_founded is not None and current_founded.tzinfo
                else current_founded
            )
            founded_naive = founded_at.astimezone(UTC).replace(tzinfo=None)
            if current_naive != founded_naive:
                row.founded_at = founded_at
                founded_changed = True
        still_in_cup = team.get("still_in_cup")
        if still_in_cup is not None:
            row.still_in_cup = bool(still_in_cup)
            cup = team.get("current_cup") if still_in_cup else None
            row.current_cup_id = cup.get("ht_cup_id") if cup else None
            row.current_cup_name = (cup.get("cup_name") or None) if cup else None
            row.current_cup_league_level = cup.get("cup_league_level") if cup else None
            row.current_cup_level = cup.get("cup_level") if cup else None
            row.current_cup_level_index = cup.get("cup_level_index") if cup else None
            row.current_cup_match_round = (
                cup.get("match_round") if cup and cup.get("match_round", -1) >= 0 else None
            )
            row.current_cup_match_rounds_left = (
                cup.get("match_rounds_left")
                if cup and cup.get("match_rounds_left", -1) >= 0
                else None
            )
        after = (
            row.name,
            row.league_name,
            row.series_name,
            row.series_ht_id,
            row.ht_league_id,
            row.ht_youth_team_id,
            row.still_in_cup,
            row.current_cup_id,
            row.current_cup_match_round,
            row.current_cup_match_rounds_left,
        )
        if before == after and not founded_changed:
            result.unchanged += 1
        else:
            result.snapshots_written += 1

    async def _persist_staff(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        file: str,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        from app.domain.value_objects.ht_constants import STAFF_TYPE_TO_FIELD

        row = await self._staff_row(uow, sync_id, team_id, captured_at)
        if file == "club":
            # HL-2xx, 2026-08-12: club.xml v1.1 ya no trae niveles agregados
            # por puesto (verificado en vivo), solo la inversión juvenil.
            row.youth_investment = payload.get("youth_investment", 0)
            row.youth_level = payload.get("youth_level", 0)
        else:  # stafflist
            tr = payload.get("trainer", {})
            # Defensivo: CHPP omite <Trainer> por completo en algunas
            # respuestas (verificado en vivo), sin esta guarda, esa
            # ausencia resetearía silenciosamente nivel/tipo/liderazgo del
            # entrenador a 0 en cada sync, igual que el bug ya conocido y
            # evitado para los campos de playerdetails.
            if tr:
                row.trainer_skill_level = tr.get("skill_level", 0)
                row.trainer_type = tr.get("trainer_type", 2)
                row.trainer_leadership = tr.get("leadership", 0)

            # El desglose real de staff (persona por persona) vive aquí, no
            # en club.xml, se agrupa por StaffType para llenar las mismas 7
            # columnas de antes, ahora con datos reales, y se guarda el
            # roster completo para mostrar "2 asistentes de nivel 5 cada
            # uno" en vez de solo la suma. Igual que con `roster` en
            # players.xml: una lista vacía no dispara un recálculo, sería
            # borrar el staff real conocido por un fetch vacío/roto.
            members = payload.get("staff_members", [])
            if members:
                for field in STAFF_TYPE_TO_FIELD.values():
                    setattr(row, field, 0)
                for member in members:
                    # Otro nombre que el del bucle de arriba: alli `field` era
                    # siempre un texto, y aqui puede faltar.
                    campo = STAFF_TYPE_TO_FIELD.get(member.get("staff_type", -1))
                    if campo is not None:
                        setattr(row, campo, getattr(row, campo) + member.get("level", 0))
                row.staff_members_json = json.dumps(members)
        row.content_hash = dict_hash(
            {
                "a": row.assistant_trainer_levels,
                "t": row.trainer_skill_level,
                "tt": row.trainer_type,
                "fc": row.form_coach_levels,
                "md": row.medic_levels,
                "members": row.staff_members_json,
            }
        )
        result.snapshots_written += 1

    async def _staff_row(
        self, uow: UnitOfWork, sync_id: int, team_id: int, captured_at: datetime
    ) -> Any:
        """La misma fila de staff para este sync: club y stafflist son ficheros
        distintos que rellenan campos distintos de un único snapshot.

        HL-2xx, 2026-08-12: una fila NUEVA arranca copiando la ÚLTIMA fila
        conocida del equipo, no en blanco, mismo patrón que ya usa
        `append_snapshot` para career_assists/last_match en jugadores. Sin
        esto, un sync que sólo trajera `club` (o un `stafflist` con
        `<Trainer>` ausente, riesgo real verificado en vivo) resetearía a 0
        el staff/entrenador ya conocido, porque cada sync crea su propia
        fila."""
        from sqlalchemy import select

        from app.domain.value_objects.ht_constants import STAFF_TYPE_TO_FIELD
        from app.infrastructure.db import models as m

        row = await uow.session.scalar(
            select(m.StaffSnapshot).where(
                m.StaffSnapshot.sync_id == sync_id, m.StaffSnapshot.team_id == team_id
            )
        )
        if row is None:
            last = await uow.session.scalar(
                select(m.StaffSnapshot)
                .where(m.StaffSnapshot.team_id == team_id)
                .order_by(m.StaffSnapshot.captured_at.desc())
                .limit(1)
            )
            row = m.StaffSnapshot(
                sync_id=sync_id,
                team_id=team_id,
                captured_at=captured_at,
                content_hash=b"\x00" * 32,
            )
            if last is not None:
                for field in STAFF_TYPE_TO_FIELD.values():
                    setattr(row, field, getattr(last, field))
                row.trainer_skill_level = last.trainer_skill_level
                row.trainer_type = last.trainer_type
                row.trainer_leadership = last.trainer_leadership
                row.youth_investment = last.youth_investment
                row.youth_level = last.youth_level
                row.staff_members_json = last.staff_members_json
            uow.session.add(row)
        return row
