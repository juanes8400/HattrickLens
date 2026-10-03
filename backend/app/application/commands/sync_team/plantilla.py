"""La plantilla: subidas, etapas y quien llega.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from datetime import datetime
from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    SyncResult,
    _as_change_row,
)
from app.domain.engines.sync_diff import diff_player_arrival
from app.domain.ports.repositories import UnitOfWork


class PlantillaMixin(BaseDeSync):
    """La plantilla: subidas, etapas y quien llega."""

    async def _persist_skill_ups(
        self,
        uow: UnitOfWork,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """Idempotente: un mismo pop (jugador, habilidad, nivel nuevo) no se
        cuenta dos veces aunque el fichero se sincronice varias veces."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        for ev in payload.get("skill_ups", []):
            exists = await uow.session.scalar(
                select(m.SkillUp.id).where(
                    m.SkillUp.ht_player_id == ev["ht_player_id"],
                    m.SkillUp.skill_id == ev["skill_id"],
                    m.SkillUp.new_level == ev["new_level"],
                )
            )
            if exists:
                result.unchanged += 1
                continue
            uow.session.add(
                m.SkillUp(
                    team_id=team_id,
                    ht_player_id=ev["ht_player_id"],
                    skill_id=ev["skill_id"],
                    old_level=ev["old_level"],
                    new_level=ev["new_level"],
                    season=ev["season"],
                    match_round=ev["match_round"],
                    day_number=ev.get("day_number", 0),
                    recorded_at=captured_at,
                )
            )
            result.snapshots_written += 1

    async def _desbloquear_habilidades(
        self, result: SyncResult, academia: int | None = None
    ) -> None:
        """Revela las habilidades de TODOS los juveniles, en una sola llamada.

        `actionType=unlockskills` no lleva `youthPlayerID`: destapa el equipo
        juvenil entero de una vez. Es gratis y no tiene tope, así que va en
        cada sincronizacion --dicho asi por el usuario el 2026-08-26-- y
        siempre ANTES de pedir `details`, que es quien lee los niveles: al
        reves se desbloquearia despues de haber leido y la revelacion no se
        veria hasta la siguiente vez.

        Es una accion de ESCRITURA y necesita el permiso
        `manage_youthplayers` (`settings.chpp_scope`). Un token emitido sin
        ese permiso contesta 401 --con una pagina de IIS, no un error XML,
        que despista-- y la unica salida es reconectar. Por eso el fallo aqui
        NO aborta nada: se anota y el sync sigue con lo que ya sabia. Perder
        la revelacion es molesto; perder la sincronizacion entera por ella
        seria peor.
        """
        # SIN EL ID DE LA CANTERA NO SE LLAMA (2026-09-27, instruccion del
        # usuario: ninguna consulta se manda sin decir de que club es).
        #
        # Antes se mandaba igual, sin `youthTeamId`, y entonces Hattrick lo
        # resuelve por el token: el club PRINCIPAL de la cuenta. Y esto no es
        # una lectura, es una ESCRITURA: sincronizar el segundo club revelaba
        # las habilidades de los juveniles del primero. Mejor no revelar --se
        # revela en la siguiente, cuando ya se sepa cual es la academia-- que
        # escribir en el club equivocado.
        if not academia:
            result.errors.append(
                "unlockskills: no se revelaron las habilidades juveniles porque "
                "todavia no se sabe cual es la academia de este club; se hara "
                "en la proxima sincronizacion"
            )
            return
        try:
            await self._chpp.fetch(
                "youthplayerlist",
                "latest",
                actionType="unlockskills",
                youthTeamId=academia,
            )
        except Exception as exc:  # noqa: BLE001, la revelacion es opcional
            result.errors.append(
                "unlockskills: no se pudieron revelar las habilidades juveniles "
                f"({exc.__class__.__name__}). Si es un 401, reconecta con "
                "Hattrick: el permiso se concede al autorizar."
            )

    async def _anunciar_altas(self, uow: UnitOfWork, team_id: int, result: SyncResult) -> None:
        """Escribe la frase de alta de cada jugador que entró en este sync.

        Tres datos, y cada uno puede faltar sin que los otros dejen de darse:

        - El PRECIO sale del libro de transferencias, buscando la compra más
          reciente de ese jugador por este club. Si el fichaje se cerró y el
          libro aún no lo trae, la frase sale sin precio y no vuelve a
          intentarse: el texto se congela en la fila, como todo en «Cambios».
        - LA CANTERA se reconoce por el bono de club de origen, que Hattrick
          sólo pone a quien subió de la propia academia. Es el único origen
          que se puede afirmar sin el libro.
        - EL SUELDO viene en la propia ficha. Los dos dineros se dividen por
          la tasa del país, como en el resto de la aplicación.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        tasa = (equipo.currency_rate or 1.0) if equipo else 1.0
        moneda = (equipo.currency_name if equipo else "") or ""

        def _dinero(v: int | None) -> int | None:
            if not v:
                return None
            return int(round(v / tasa)) if tasa else int(v)

        ids = [p["ht_player_id"] for _, p in result.arrived_players]
        compras: dict[int, int] = {}
        if ids:
            filas = (
                (
                    await uow.session.execute(
                        select(m.TeamTransfer)
                        .where(
                            m.TeamTransfer.team_id == team_id,
                            m.TeamTransfer.is_buy.is_(True),
                            m.TeamTransfer.ht_player_id.in_(ids),
                        )
                        .order_by(m.TeamTransfer.deadline)
                    )
                )
                .scalars()
                .all()
            )
            # Ordenadas de vieja a nueva, así que la última que se escribe es
            # la más reciente: quien vuelve al club por segunda vez sale con
            # el precio de ESTA vuelta y no con el de la primera.
            for f in filas:
                compras[f.ht_player_id] = f.price

        for nombre, p in result.arrived_players:
            cambio = diff_player_arrival(
                nombre,
                salary=_dinero(p.get("salary")),
                purchase_price=_dinero(compras.get(p["ht_player_id"])),
                from_academy=bool(p.get("mother_club_bonus")),
                currency=moneda,
                ht_player_id=p["ht_player_id"],
            )
            result.changes.append(_as_change_row(cambio))

    async def _reconstruir_etapas(self, uow: UnitOfWork, team_id: int) -> int:
        """Rehace las etapas del club a partir del libro de transferencias.

        La regla es la que cuenta Hattrick: una compra nuestra ABRE una etapa y
        la venta siguiente la CIERRA. Una venta sin compra delante es alguien
        que no compramos -un canterano, casi siempre-, asi que abre y cierra
        etapa a la vez, marcada como llegada de cantera.

        Se rehace entero cada vez, porque es una derivacion: lo unico que no se
        puede recalcular -los partidos ya censados, lo que el usuario atribuyo
        a mano y las etapas que decidio excluir- se conserva emparejando por el
        identificador de la transferencia, que Hattrick no reutiliza.
        """
        from sqlalchemy import delete, select

        from app.infrastructure.db import models as m

        movimientos = (
            (
                await uow.session.execute(
                    select(m.TeamTransfer)
                    .where(m.TeamTransfer.team_id == team_id)
                    .order_by(m.TeamTransfer.ht_player_id, m.TeamTransfer.deadline)
                )
            )
            .scalars()
            .all()
        )
        if not movimientos:
            return 0

        anteriores = (
            (
                await uow.session.execute(
                    select(m.PlayerStint).where(m.PlayerStint.team_id == team_id)
                )
            )
            .scalars()
            .all()
        )

        def clave(etapa: Any) -> tuple[int, int | None, int | None]:
            return (
                etapa.ht_player_id,
                etapa.arrival_transfer_id,
                etapa.sale_transfer_id,
            )

        guardado = {clave(e): e for e in anteriores}
        jugadores = {
            p.ht_player_id: p
            for p in (
                await uow.session.execute(select(m.Player).where(m.Player.team_id == team_id))
            )
            .scalars()
            .all()
        }
        de_quien = await self._fichas_de_los_sin_identificador(uow, team_id, movimientos, jugadores)

        def a_quien_pertenece(mov: Any) -> int:
            """El identificador de la PERSONA, que en un huerfano no es el suyo."""
            duenio: int = de_quien.get(mov.ht_transfer_id, mov.ht_player_id)
            return duenio

        # Reordenar por persona: los huerfanos de un mismo nombre tienen cada
        # uno un numero distinto, asi que el orden que venia de la consulta los
        # dejaba separados y la compra no encontraba a su venta.
        movimientos = sorted(movimientos, key=lambda x: (a_quien_pertenece(x), x.deadline))

        await uow.session.execute(delete(m.PlayerStint).where(m.PlayerStint.team_id == team_id))
        await uow.session.flush()

        nuevas: list[Any] = []
        abierta: dict[int, Any] = {}
        for mov in movimientos:
            de_la_persona = a_quien_pertenece(mov)
            jugador = jugadores.get(de_la_persona)
            if jugador is None:
                continue
            if mov.is_buy:
                etapa = m.PlayerStint(
                    player_id=jugador.id,
                    ht_player_id=de_la_persona,
                    team_id=team_id,
                    arrived_at=mov.deadline,
                    arrival_price=mov.price,
                    arrival_transfer_id=mov.ht_transfer_id,
                )
                abierta[de_la_persona] = etapa
                nuevas.append(etapa)
                continue

            etapa = abierta.pop(de_la_persona, None)
            if etapa is None:
                # Vendido sin haberlo comprado. Casi siempre es un canterano,
                # pero no cuando el identificador es prestado: de esos no se
                # sabe de donde salieron, y darlos por cantera meteria como
                # gratis a gente que costo dinero.
                prestado = jugador.ht_player_id_is_transfer
                etapa = m.PlayerStint(
                    player_id=jugador.id,
                    ht_player_id=de_la_persona,
                    team_id=team_id,
                    from_academy=not prestado,
                    unknown_origin=prestado,
                )
                nuevas.append(etapa)
            etapa.left_at = mov.deadline
            etapa.sale_price = mov.price
            etapa.sale_transfer_id = mov.ht_transfer_id
            etapa.buyer_team_id = mov.counterpart_team_id

        # Quien se fue sin que nadie lo comprara no deja venta en el libro: su
        # etapa se cierra con la fecha en que desaparecio de la plantilla y sin
        # precio. Sin esto quedaria abierta para siempre, como si siguiera en
        # el club.
        for ht_player_id, etapa in abierta.items():
            jugador = jugadores.get(ht_player_id)
            if jugador is not None and jugador.left_team_at is not None:
                etapa.left_at = jugador.left_team_at

        for etapa in nuevas:
            previa = guardado.get(clave(etapa))
            if previa is None:
                continue
            # Lo que no se puede recalcular viaja con la etapa.
            etapa.games_played_for_us = previa.games_played_for_us
            etapa.games_computed_at = previa.games_computed_at
            etapa.excluded = previa.excluded
            etapa.training_type_manual = previa.training_type_manual
            etapa.top_skill_manual = previa.top_skill_manual
            etapa.age_years_manual = previa.age_years_manual
            etapa.age_days_manual = previa.age_days_manual

        uow.session.add_all(nuevas)
        await uow.session.flush()
        await self._cuadrar_fichas_prestadas(uow, team_id, nuevas, jugadores)
        return len(nuevas)
