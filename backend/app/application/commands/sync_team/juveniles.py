"""La cantera y sus ojeadores.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    ProgressReporter,
    SyncResult,
    _full_player_name,
    _nombre_legible,
    _parse_dt,
    _report,
)
from app.domain.ports.repositories import UnitOfWork


class JuvenilesMixin(BaseDeSync):
    """La cantera y sus ojeadores."""

    async def _persist_youth(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """Plantilla juvenil, mismo patrón append-only que la plantilla
        principal: identidad estable en `youth_players`, un snapshot nuevo
        sólo cuando algo cambió de verdad (hash del contenido).

        2026-08-15: hasta hoy nadie descargaba `youthplayerlist`, así que la
        pantalla de Juveniles tenía toda la lógica construida (categorías,
        potencial, plazos, ROI) alimentándose de una tabla vacía.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        roster = payload.get("youth_players", [])
        seen_ids: set[int] = set()

        for row in roster:
            ht_id = row.get("ht_youth_player_id", 0)
            if not ht_id:
                continue
            seen_ids.add(ht_id)

            youth = await uow.session.scalar(
                select(m.YouthPlayer).where(m.YouthPlayer.ht_youth_player_id == ht_id)
            )
            if youth is None:
                youth = m.YouthPlayer(
                    ht_youth_player_id=ht_id,
                    team_id=team_id,
                    first_name=row.get("first_name", ""),
                    last_name=row.get("last_name", ""),
                    arrived_at=_parse_dt(row.get("arrival_date")),
                    specialty=row.get("specialty") or 0,
                )
                uow.session.add(youth)
                await uow.session.flush()
            else:
                youth.first_name = row.get("first_name") or youth.first_name
                youth.last_name = row.get("last_name") or youth.last_name
                # Se refresca también en los que ya estaban: es como se llena
                # la columna en los canteranos anteriores a la migración 0077.
                youth.specialty = row.get("specialty") or 0
                # Si había salido y vuelve a aparecer, sigue en la academia.
                youth.left_at = None
                # Y si estaba apuntado a otro club de la cuenta, vuelve al
                # suyo: el juvenil pertenece al club cuya lista lo trae. Asi
                # se repara solo lo que sembro la cantera compartida.
                youth.team_id = team_id

            values = {f: row.get(f) for f in self.YOUTH_SNAPSHOT_FIELDS}
            new_hash = hashlib.sha256(
                json.dumps(values, sort_keys=True, default=str).encode()
            ).digest()
            last = await uow.session.scalar(
                select(m.YouthSnapshot)
                .where(m.YouthSnapshot.youth_player_id == youth.id)
                .order_by(m.YouthSnapshot.captured_at.desc(), m.YouthSnapshot.id.desc())
                .limit(1)
            )
            if last is not None and last.content_hash == new_hash:
                result.unchanged += 1
                continue

            uow.session.add(
                m.YouthSnapshot(
                    sync_id=sync_id,
                    youth_player_id=youth.id,
                    captured_at=captured_at,
                    content_hash=new_hash,
                    **{k: (v if v is not None else None) for k, v in values.items()},
                )
            )
            result.snapshots_written += 1

        # Quien ya no viene en el fichero salió de la academia (promocionado,
        # vendido o descartado). Mismo criterio que la plantilla principal: un
        # roster vacío NO marca a todos como salidos, sería un fetch roto.
        if roster:
            gone = list(
                (
                    await uow.session.execute(
                        select(m.YouthPlayer).where(
                            m.YouthPlayer.team_id == team_id,
                            m.YouthPlayer.left_at.is_(None),
                            m.YouthPlayer.ht_youth_player_id.notin_(seen_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for youth in gone:
                youth.left_at = captured_at

    async def _persist_ojeadores(
        self,
        uow: UnitOfWork,
        team_id: int,
        ojeadores: list[dict[str, Any]],
        captured_at: datetime,
    ) -> None:
        """El censo de ojeadores, para poder hacerles la cuenta.

        Lo que importa aqui es lo que Hattrick NO dice: cuando se despide a un
        ojeador, simplemente desaparece de la lista y no queda ni rastro ni
        fecha. Por eso se anota `last_seen_at` en cada pasada y, cuando uno
        falta, se cierra su `gone_at` en la ultima vez que se le vio. Su ultimo
        tramo de coste queda aproximado, con el error acotado a lo que se tarde
        entre dos sincronizaciones.

        Y no se borra a nadie: un ojeador despedido se queda en la tabla con su
        saldo final. Borrarlo haria desaparecer de la pantalla los canteranos
        que trajo, que es justo lo que se quiere recordar.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        vistos = {int(o["ht_scout_id"]) for o in ojeadores if o.get("ht_scout_id")}
        guardados = {
            f.ht_scout_id: f
            for f in (
                await uow.session.execute(
                    select(m.YouthScout).where(m.YouthScout.team_id == team_id)
                )
            ).scalars()
        }

        for o in ojeadores:
            ht_id = int(o.get("ht_scout_id") or 0)
            if not ht_id:
                continue
            fila = guardados.get(ht_id)
            if fila is None:
                fila = m.YouthScout(team_id=team_id, ht_scout_id=ht_id, name="")
                uow.session.add(fila)
            fila.name = o.get("name") or fila.name or ""
            fila.region_name = o.get("region_name") or fila.region_name
            fila.hired_at = _parse_dt(o.get("hired_date")) or fila.hired_at
            fila.last_seen_at = captured_at
            # Si vuelve a aparecer, ya no se fue: pudo ser un fallo de lectura.
            fila.gone_at = None

        for ht_id, fila in guardados.items():
            if ht_id not in vistos and fila.gone_at is None:
                fila.gone_at = fila.last_seen_at

    async def _sync_informes_de_ojeador(
        self,
        uow: UnitOfWork,
        team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> int:
        """Quien trajo a cada canterano, y que queda por revelarle.

        2026-08-24. Cuesta una llamada por canterano.

        Se refresca a quien no tiene informe y a quien ha cambiado algo desde
        la última vez, porque `MayUnlock` se apaga en cuanto esa habilidad se
        revela.

        2026-09-14, pedido del usuario: el MENSAJE DEL OJEADOR --quién lo
        trajo, desde dónde y qué dijo al llegar-- se pide y se guarda UNA sola
        vez, con el primer informe, y no se vuelve a preguntar jamás: no cambia
        nunca. Los refrescos siguientes se piden sin `showScoutCall` y sólo
        actualizan `MayUnlock`.
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        ultima_foto = (
            select(
                m.YouthSnapshot.youth_player_id,
                sa_func.max(m.YouthSnapshot.captured_at).label("cuando"),
            )
            .group_by(m.YouthSnapshot.youth_player_id)
            .subquery()
        )
        filas = (
            await uow.session.execute(
                select(m.YouthPlayer, m.YouthScoutReport, ultima_foto.c.cuando)
                .join(ultima_foto, ultima_foto.c.youth_player_id == m.YouthPlayer.id)
                .outerjoin(
                    m.YouthScoutReport,
                    m.YouthScoutReport.youth_player_id == m.YouthPlayer.id,
                )
                .where(m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None))
            )
        ).all()

        pendientes = [
            (juvenil, informe)
            for juvenil, informe, cuando in filas
            if informe is None or (cuando is not None and cuando > informe.fetched_at)
        ]
        if not pendientes:
            return 0

        ahora = datetime.now(UTC).replace(tzinfo=None)
        traidos = 0
        for juvenil, informe in pendientes:
            nombre = _full_player_name(juvenil.first_name, juvenil.last_name)
            await _report(
                on_progress,
                f"Informe del ojeador sobre {nombre}...",
            )
            primera_vez = informe is None
            try:
                # El mensaje del ojeador sólo se pide la primera vez.
                parametros = {"showScoutCall": "true"} if primera_vez else {}
                ficha = await self._chpp.fetch(
                    "youthplayerdetails",
                    "1.0",
                    youthPlayerId=juvenil.ht_youth_player_id,
                    **parametros,
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"{_nombre_legible('youthplayerdetails')} {juvenil.ht_youth_player_id}: {exc}"
                )
                continue
            if not ficha:
                continue
            datos: dict[str, Any] = {
                "may_unlock_json": json.dumps(ficha.get("may_unlock") or {}, ensure_ascii=False),
                "fetched_at": ahora,
            }
            if primera_vez:
                datos |= {
                    "scout_id": ficha.get("scout_id"),
                    "scout_name": ficha.get("scout_name") or "",
                    "scouting_region_id": ficha.get("scouting_region_id"),
                    "comments_json": json.dumps(
                        ficha.get("scout_comments") or [], ensure_ascii=False
                    ),
                }
            if informe is None:
                uow.session.add(m.YouthScoutReport(youth_player_id=juvenil.id, **datos))
            else:
                for campo, valor in datos.items():
                    setattr(informe, campo, valor)
            traidos += 1
            result.snapshots_written += 1
        return traidos

    async def _sync_antiguos_canteranos(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
    ) -> int:
        """Los canteranos que ya pasaron por el primer equipo.

        `players.xml` con `actionType=viewOldies` --senalado por el usuario el
        2026-08-26--: devuelve los ex-canteranos con su identificador de
        MAYORES. Comprobado contra la cuenta real: los 43 que devuelve casan
        uno a uno, por identificador, con los que ya teniamos marcados como
        canteranos. Es el puente que faltaba entre la academia y las ventas.

        Se guarda tal cual llega y nada mas: son jugadores que en su mayoria ya
        no son nuestros, y las reglas de CHPP permiten enseñar su estado ACTUAL
        pero no llevarles un historial.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        try:
            payload = await self._chpp.fetch(
                "players",
                version=FILE_VERSIONS["players"],
                parse_as="players_viewoldies",
                actionType="viewOldies",
                teamID=ht_team_id,
            )
        except Exception as exc:  # noqa: BLE001, best effort, se reintenta
            result.errors.append(f"{_nombre_legible('viewOldies')}: {exc}")
            return 0

        filas = payload.get("players", [])
        if not filas:
            return 0

        guardados = {
            f.ht_player_id: f
            for f in (
                await uow.session.execute(
                    select(m.FormerYouthPlayer).where(m.FormerYouthPlayer.team_id == team_id)
                )
            ).scalars()
        }
        for p_ in filas:
            ht_id = p_.get("ht_player_id")
            if not ht_id:
                continue
            fila = guardados.get(ht_id)
            if fila is None:
                fila = m.FormerYouthPlayer(team_id=team_id, ht_player_id=ht_id, name="")
                uow.session.add(fila)
            nombre = f"{p_.get('first_name', '')} {p_.get('last_name', '')}".strip()
            fila.name = nombre or fila.name
            fila.current_team_name = p_.get("team_name") or fila.current_team_name
            fila.current_tsi = p_.get("tsi") if p_.get("tsi") is not None else fila.current_tsi
            # `ArrivalDate` es «the date of arrival to current team»: cuando
            # llego al club donde esta HOY, que salvo que siga con nosotros
            # no es el nuestro. NO es la fecha de ascenso, aunque durante
            # meses se guardo como si lo fuera (2026-08-31).
            fila.arrived_at_current_team = (
                _parse_dt(p_.get("arrival_date")) or fila.arrived_at_current_team
            )
        return len(filas)
