"""Alineaciones, las jugadas y las ordenes del proximo.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

import json
from datetime import UTC, datetime, timedelta

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    MATCHLINEUP_ROLE_VERSION,
    ProgressReporter,
    SyncResult,
    _nombre_legible,
    _report,
    _tras_fallo,
)
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_constants import (
    MATCHLINEUP_SPECIAL_ROLES,
    is_competitive_match_type,
)

#: Los puestos del once en `MatchRoleID`: portero, defensas, medios y
#: delanteros. Del 114 en adelante empieza el banquillo.
ROLES_DEL_ONCE = range(100, 114)

#: Cuántos tiene que haber para que Hattrick calcule los ratings.
TITULARES = 11


def _cubiertos_en_el_campo(posiciones: object) -> int:
    """Cuántos puestos del once traen jugador.

    Hattrick OMITE los vacíos en vez de mandarlos con el jugador a cero, así
    que un hueco sólo se ve contando: la alineación llega con menos de once
    entradas y sin decir cuál falta. Por eso el aviso habla del número y no
    del puesto: decir «falta el mediocentro izquierdo» sería adivinar, porque
    los identificadores que no aparecen pueden ser los que esa formación no
    usa (2026-10-07).
    """
    if not isinstance(posiciones, list):
        return 0
    cubiertos = 0
    for puesto in posiciones:
        if not isinstance(puesto, dict):
            continue
        try:
            rol = int(puesto.get("role_id") or 0)
            jugador = int(puesto.get("ht_player_id") or 0)
        except (TypeError, ValueError):
            continue
        if rol in ROLES_DEL_ONCE and jugador > 0:
            cubiertos += 1
    return cubiertos


class AlineacionMixin(BaseDeSync):
    """Alineaciones, las jugadas y las ordenes del proximo."""

    async def _sync_alineaciones_jugadas(
        self,
        uow: UnitOfWork,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """El once que de verdad salio, pedido despues del partido.

        2026-09-27, caso del usuario: el partido 770393948 del FC Villainy
        salia en Equipo con ocho jugadores y una formacion «3-5-0».

        `_sync_upcoming_match_orders` guarda las ORDENES, y solo puede hacerlo
        mientras el partido sigue PROXIMO y con ordenes dadas: es una ventana
        que se cierra y no vuelve. Un segundo equipo que se sincroniza cada
        pocas semanas se queda sin ellas en casi todos sus partidos, y entonces
        el once tenia que salir de las fichas de los jugadores, que se pisan en
        cuanto juegan otro partido, aunque sea un amistoso.

        Un partido ya jugado, en cambio, es un hecho publico y permanente:
        `matchlineup.xml` lo sirve cuando sea. Se pide UNA vez por partido, se
        guarda, y no se vuelve a pedir nunca.

        SE GUARDA EL ONCE INICIAL, no el final: `<StartingLineup>`, que trae
        los once que salieron con su puesto y su orden. `<Lineup>` no sirve
        para esto aunque lo parezca, porque en la version 2.1 es el estado
        TRAS los cambios (ver el comentario del bucle, con el caso real).
        """
        from sqlalchemy import or_, select

        from app.infrastructure.db import models as m

        pendientes = (
            (
                await uow.session.execute(
                    select(m.Match)
                    .where(
                        or_(
                            m.Match.home_team_ht_id == ht_team_id,
                            m.Match.away_team_ht_id == ht_team_id,
                        ),
                        m.Match.status.ilike("finished"),
                        m.Match.played_lineup_json.is_(None),
                    )
                    .order_by(m.Match.played_at.desc())
                    # Un puñado de candidatos, no solo los que caben: el que
                    # de verdad hace falta puede no ser el mas reciente, ver
                    # abajo. El tope es para no traerse anos de archivo.
                    .limit(self.CANDIDATOS_DE_ALINEACION)
                )
            )
            .scalars()
            .all()
        )

        # Todo sin zona, que es como `UtcDateTime` devuelve las fechas: comparar
        # una de la base contra un `datetime.now(UTC)` revienta con "can't
        # subtract offset-naive and offset-aware datetimes".
        def _cuando(partido: m.Match) -> datetime:
            cuando: datetime = partido.played_at
            return cuando.replace(tzinfo=None) if cuando.tzinfo else cuando

        corte = captured_at.astimezone(UTC).replace(tzinfo=None) - timedelta(
            days=self.DIAS_DE_ALINEACIONES
        )

        # EL OFICIAL MAS RECIENTE VA PRIMERO, y no el mas reciente a secas
        # (2026-09-28, senalado en la revision de la PR). Equipo enseña «tu
        # ultima formacion oficial», que es el ultimo partido COMPETITIVO: si
        # despues de el hay tres amistosos o escaleras, ordenando solo por
        # fecha el presupuesto de la sincronizacion se gastaba entero en esos
        # tres y el que se enseña en pantalla no llegaba a pedirse nunca. Es
        # decir, justo el partido por el que se escribio todo esto.
        oficial = next((p for p in pendientes if is_competitive_match_type(p.match_type)), None)
        resto = [p for p in pendientes if p is not oficial and _cuando(p) >= corte]
        # El oficial se pide tenga la edad que tenga; los demas, SOLO si son
        # recientes, sin excepciones. Antes el mas reciente a secas tambien se
        # colaba siempre, y eso traia un amistoso de hace un ano por delante de
        # nada. Si un club no tiene ningun partido oficial, aqui no se pide
        # nada, que es correcto: Equipo tampoco tiene entonces que enseñar.
        pendientes = ([oficial] if oficial is not None else []) + resto
        pendientes = pendientes[: self.ALINEACIONES_POR_SYNC]

        for match in pendientes:
            await _report(
                on_progress,
                f"Descargando la alineación del partido {match.ht_match_id}...",
            )
            try:
                payload = await self._chpp.fetch(
                    "matchlineup",
                    version=MATCHLINEUP_ROLE_VERSION,
                    matchID=match.ht_match_id,
                    matchType=match.match_type,
                    teamID=ht_team_id,
                )
            except Exception as exc:  # noqa: BLE001
                # Se anota y se sigue: un partido que Hattrick no sirva no
                # puede tumbar la sincronizacion, pero tampoco se calla, que
                # es como este mismo fichero se trago un NameError meses.
                result.errors.append(f"alineación del partido {match.ht_match_id}: {exc}")
                continue

            # DE `<StartingLineup>` Y NO DE `<Lineup>`. La primera version de
            # esto cruzaba `<Lineup>` con la lista de titulares, y en el primer
            # partido real contra Hattrick (matchID 770453142) salio un once
            # con RoleID 19 --papel de balon parado-- en vez del 101 del
            # lateral: `<Lineup>` es el estado FINAL, asi que al titular
            # sustituido le habia quitado su puesto para darselo al suplente
            # que entro, y de el solo quedaba su fila de papel especial.
            # `<StartingLineup>` trae PlayerID, RoleID y Behaviour del once que
            # salio, que es exactamente lo que hace falta.
            #
            # Y fuera los papeles especiales. `<StartingLineup>` repite al
            # titular que tira los balones parados o lleva el brazalete, con
            # RoleID 17-21 y siempre despues de su fila real: en el partido de
            # arriba venian doce filas para once jugadores.
            once = [
                {
                    "ht_player_id": int(j["ht_player_id"]),
                    "role_id": int(j.get("role_id") or 0),
                    "behaviour": int(j.get("behaviour") or 0),
                }
                for j in payload.get("starting_players") or []
                if j.get("ht_player_id")
                and int(j.get("role_id") or 0) not in MATCHLINEUP_SPECIAL_ROLES
            ]
            # Sin `<StartingLineup>` (una version vieja, un partido raro) mejor
            # no guardar nada que guardar algo que no es el once.
            if len(once) < 9:
                continue
            match.played_lineup_json = json.dumps(
                once, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            # Y lo que paso DESPUES del pitido inicial, que venia en la misma
            # respuesta y se tiraba (2026-10-09). Sin los cambios, un jugador
            # que paso de lateral a extremo en el minuto 87 entraba al
            # entrenamiento como extremo los noventa minutos.
            #
            # Se guarda aunque venga vacio --un partido sin cambios es una
            # respuesta valida-- para distinguir «no hubo» de «no se ha pedido
            # todavia», que es lo que decide si se puede repartir por puestos.
            match.played_events_json = json.dumps(
                {
                    "cambios": [
                        {
                            "minuto": int(c.get("minuto") or 0),
                            "sale": int(c.get("sale") or 0),
                            "entra": int(c.get("entra") or 0),
                            "nuevo_puesto": int(c.get("nuevo_puesto") or 0),
                            "order_type": int(c.get("order_type") or 0),
                        }
                        for c in payload.get("substitutions") or []
                    ],
                    "cobrador": int(payload.get("set_pieces_taker") or 0),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            match.played_lineup_captured_at = captured_at

    async def _sync_upcoming_match_orders(
        self,
        uow: UnitOfWork,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Guarda las órdenes realmente enviadas de próximos partidos propios.

        `matches.xml.OrdersGiven` es el gate oficial: solo cuando vale True
        pedimos `matchorders.xml` 3.0. Así nunca confundimos la alineación por
        defecto del formulario con una decisión ya enviada por el manager.
        Mientras el partido siga próximo se vuelve a consultar en cada sync,
        porque Hattrick permite modificar las órdenes antes del cierre.
        """
        from sqlalchemy import or_, select

        from app.infrastructure.db import models as m

        pending = (
            (
                await uow.session.execute(
                    select(m.Match)
                    .where(
                        or_(
                            m.Match.home_team_ht_id == ht_team_id,
                            m.Match.away_team_ht_id == ht_team_id,
                        ),
                        m.Match.orders_given.is_(True),
                        m.Match.status.ilike("upcoming"),
                    )
                    .order_by(m.Match.played_at)
                )
            )
            .scalars()
            .all()
        )

        for match in pending:
            await _report(
                on_progress,
                f"Descargando alineación enviada del partido {match.ht_match_id}...",
            )
            source_system = (match.source_system or "hattrick").strip().lower()
            if source_system not in {"hattrick", "youth", "htointegrated"}:
                source_system = "hattrick"
            try:
                payload = await self._chpp.fetch(
                    "matchorders",
                    version=FILE_VERSIONS["matchorders"],
                    matchID=match.ht_match_id,
                    # De QUE club son las ordenes. Sin esto lo decide el token,
                    # y el token es la cuenta, no el club: con dos clubes en la
                    # misma cuenta contesta el principal. Comprobado en vivo el
                    # 2026-09-27: con el id del rival el fichero vuelve sin
                    # posiciones y con el propio con las once, asi que lo
                    # respeta y dejarlo fuera era pedirle que adivinara.
                    teamId=ht_team_id,
                    sourceSystem=source_system,
                )
                if payload.get("ht_match_id") != match.ht_match_id:
                    continue
                positions = payload.get("positions", []) if payload.get("available") else []
                # Un partido puede empezar con 9-11 jugadores. Menos de 9 no
                # es una alineación válida y no debe desplazar el fallback.
                if len(positions) < 9:
                    continue
                lineup_json = json.dumps(
                    positions, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                before = (
                    match.submitted_lineup_json,
                    match.submitted_tactic_type,
                    match.submitted_attitude,
                    match.submitted_coach_modifier,
                )
                after = (
                    lineup_json,
                    payload.get("tactic_type"),
                    payload.get("attitude"),
                    payload.get("coach_modifier"),
                )
                changed = before != after
                if changed:
                    match.submitted_lineup_json = lineup_json
                    match.submitted_tactic_type = payload.get("tactic_type")
                    match.submitted_attitude = payload.get("attitude")
                    match.submitted_coach_modifier = payload.get("coach_modifier")
                    match.submitted_orders_captured_at = captured_at

                # Esta acción es una consulta GET de solo lectura. Hattrick
                # calcula los ratings de minuto 0 para las órdenes que ya
                # están guardadas; no envía ni modifica la alineación.
                try:
                    await _report(
                        on_progress,
                        f"Calculando ratings del partido {match.ht_match_id}...",
                    )
                    predicted_payload = await self._chpp.fetch(
                        "matchorders",
                        version=FILE_VERSIONS["matchorders"],
                        matchID=match.ht_match_id,
                        teamId=ht_team_id,
                        sourceSystem=source_system,
                        actionType="predictratings",
                    )
                    prediction = predicted_payload.get("prediction")
                    if predicted_payload.get("ht_match_id") == match.ht_match_id and isinstance(
                        prediction, dict
                    ):
                        ratings = prediction.get("ratings") or {}
                        predicted_before = (
                            match.submitted_tactic_skill,
                            match.submitted_rating_midfield,
                            match.submitted_rating_right_def,
                            match.submitted_rating_central_def,
                            match.submitted_rating_left_def,
                            match.submitted_rating_right_att,
                            match.submitted_rating_central_att,
                            match.submitted_rating_left_att,
                        )
                        predicted_after = (
                            prediction.get("tactic_skill"),
                            ratings.get("midfield"),
                            ratings.get("right_def"),
                            ratings.get("central_def"),
                            ratings.get("left_def"),
                            ratings.get("right_att"),
                            ratings.get("central_att"),
                            ratings.get("left_att"),
                        )
                        if predicted_before != predicted_after:
                            match.submitted_tactic_type = prediction.get("tactic_type")
                            match.submitted_tactic_skill = prediction.get("tactic_skill")
                            match.submitted_rating_midfield = ratings.get("midfield")
                            match.submitted_rating_right_def = ratings.get("right_def")
                            match.submitted_rating_central_def = ratings.get("central_def")
                            match.submitted_rating_left_def = ratings.get("left_def")
                            match.submitted_rating_right_att = ratings.get("right_att")
                            match.submitted_rating_central_att = ratings.get("central_att")
                            match.submitted_rating_left_att = ratings.get("left_att")
                            changed = True
                        # Fuera del `if`: la fecha no dice "cambiaron los
                        # ratings", dice "esta predicción corresponde a la
                        # alineación de ahora". Dentro del `if`, una predicción
                        # idéntica dejaba la fecha vieja y la vista la marcaba
                        # como desfasada sin serlo.
                        match.submitted_ratings_captured_at = captured_at
                    elif predicted_payload.get("chpp_error"):
                        # Hattrick devolvió `chpperror.xml`. Los ratings que ya
                        # están guardados pertenecen a otra alineación: no se
                        # tocan, pero el fallo se registra para que la vista
                        # pueda decir "no hay predicción" en vez de enseñar los
                        # viejos como si fueran los de este once.
                        #
                        # Y SE DICE EN CRISTIANO CUANDO SE PUEDE. Con un once
                        # incompleto Hattrick contesta «Sequence contains no
                        # matching element», que es una excepción de .NET
                        # escapándose de su servidor: no dice qué pasa ni qué
                        # hacer. Las órdenes ya las tenemos delante, así que
                        # se cuentan los puestos cubiertos y se explica
                        # (2026-10-07, visto por el usuario en un amistoso con
                        # diez jugadores en el campo).
                        cubiertos = _cubiertos_en_el_campo(payload.get("positions"))
                        if cubiertos < TITULARES:
                            detalle = (
                                f"tu alineación tiene {cubiertos} jugadores y hacen falta "
                                f"once, así que Hattrick no puede calcular los ratings"
                            )
                        else:
                            detalle = str(predicted_payload["chpp_error"])
                        result.errors.append(
                            f"{_nombre_legible('matchorders')} ({match.ht_match_id}): {detalle}"
                        )
                        result.status = "partial"
                except Exception as exc:  # noqa: BLE001, las órdenes siguen siendo útiles
                    result.errors.append(
                        f"{_nombre_legible('matchorders')} ({match.ht_match_id}): {exc}"
                    )
                    await _tras_fallo(uow, exc)
                    result.status = "partial"

                if changed:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                result.errors.append(
                    f"{_nombre_legible('matchorders')} ({match.ht_match_id}): {exc}"
                )
                await _tras_fallo(uow, exc)
                result.status = "partial"
