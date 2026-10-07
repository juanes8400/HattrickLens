"""Lo que comparten los mixins de la sincronizacion.

Las constantes de clase, los atributos que pone `__init__`, los
ayudantes chicos que usan varios sujetos, y las costuras: los metodos
que un sujeto le pide a otro.

Las costuras van bajo `TYPE_CHECKING` a proposito. Asi mypy --que corre
en estricto sobre `app/application`-- ve la llamada entre mixins, y en
ejecucion no existen: si un mixin se quedara sin implementar el suyo,
saltaria un AttributeError en vez de devolver None en silencio.
"""

import contextlib
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.application.commands.sync_team.comun import (
    SyncResult,
    mensaje_de_error,
)
from app.domain.ports.chpp_gateway import CHPPGateway
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.skill import Age


class BaseDeSync:
    """La parte comun de `SyncTeamHandler`, repartido en mixins."""

    #: Los pone `SyncTeamHandler.__init__`; se declaran para que los
    #: mixins los vean con su tipo.
    _uow: UnitOfWork
    _chpp: CHPPGateway
    _fila_en_curso: int | None
    _academia_ajena: bool

    #: Cuantos partidos jugados sin alineacion se rescatan por sincronizacion.
    #: Uno basta para la pantalla de Equipo, que solo mira el ultimo; el tope
    #: existe para que un club con anos de historia no dispare cien llamadas
    #: la primera vez. Van del mas reciente al mas viejo.
    ALINEACIONES_POR_SYNC = 3
    #: Y de los demas, solo los recientes. Sin corte, un club con doscientos
    #: partidos viejos se pasaria sesenta sincronizaciones gastando tres
    #: llamadas cada una en alineaciones que ninguna pantalla mira.
    #:
    #: EL MAS RECIENTE SE PIDE SIEMPRE, tenga la edad que tenga: es el que
    #: enseña Equipo como «tu ultima formacion oficial», y dejarlo fuera por
    #: viejo seria dejar rota justo la pantalla que motivo todo esto.
    DIAS_DE_ALINEACIONES = 60
    #: Cuantos partidos se miran para elegir esos tres. Mas que los que se
    #: piden, porque el que hace falta --el ultimo oficial-- puede tener
    #: varios amistosos por delante.
    CANDIDATOS_DE_ALINEACION = 40
    #: Cuantos partidos ya guardados recuperan su desglose por sincronizacion.
    #: Van del mas reciente al mas viejo y cuando estan todos esto no pide
    #: nada. Un club con anos de historia tardara varias sincronizaciones, que
    #: es preferible a gastarle cien llamadas de golpe.
    DESGLOSES_POR_SYNC = 10
    #: Cuantas fichas de partido ajeno se rescatan por sincronizacion. Lo
    #: normal es que no haya ninguna; el tope existe para que un usuario que
    #: llegue con cien huerfanos no pague cien llamadas de golpe.
    RESCATES_DE_PARTIDO_POR_SYNC = 20
    YOUTH_SNAPSHOT_FIELDS = (
        "age_years",
        "age_days",
        "minutes_last_match",
        "can_be_promoted_in",
        "keeper",
        "keeper_max",
        "keeper_max_reached",
        "defending",
        "defending_max",
        "defending_max_reached",
        "playmaking",
        "playmaking_max",
        "playmaking_max_reached",
        "winger",
        "winger_max",
        "winger_max_reached",
        "passing",
        "passing_max",
        "passing_max_reached",
        "scoring",
        "scoring_max",
        "scoring_max_reached",
        "set_pieces",
        "set_pieces_max",
        "set_pieces_max_reached",
    )

    async def _cerrar_como_fallida(self, exc: Exception) -> None:
        """Deja la fila de la sincronización en «failed» con el motivo.

        Con otra sesión: la de la sincronización puede ser justo la que se
        rompió. Si la base sigue caída tampoco se puede anotar, y no se insiste.
        """
        sync_id = self._fila_en_curso
        if sync_id is None:
            return
        with contextlib.suppress(Exception):
            async with self._uow as uow:
                await uow.syncs.finalize(
                    sync_id, status="failed", error=mensaje_de_error(exc)[:2000] or None
                )
                await uow.commit()

    @staticmethod
    def _es_huerfano(mov: Any) -> bool:
        """Su identificador es prestado: ES el numero de su transferencia."""
        return bool(mov.ht_player_id == mov.ht_transfer_id)

    @staticmethod
    def _nombre_para_agrupar(mov: Any) -> str:
        return (mov.player_name or "").strip()

    def _split_player_name(self, full_name: str) -> tuple[str, str]:
        """`transfersteam.xml` solo trae un `PlayerName` combinado (a
        diferencia de `players.xml`, que separa Nombre/Apellido), heurística
        de "última palabra = apellido" para crear una identidad mínima de un
        jugador que esta app nunca vio en la plantilla (ver
        `execute_transfers_history`). Cosmético: solo afecta cómo se separa
        el nombre para volver a unirlo igual (`f"{first} {last}"`) en la
        tabla Detalle, no a ningún cálculo de saldo."""
        parts = full_name.strip().rsplit(" ", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", full_name.strip()

    async def _series_ht_id(self, uow: UnitOfWork, team_id: int) -> int:
        """leaguedetails se pide por serie (LeagueLevelUnitID), no por equipo.
        Requiere haber sincronizado teamdetails antes en el mismo sync."""
        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)
        if team is None or not team.series_ht_id:
            raise ValueError(
                "no se conoce la serie del equipo: hay que traer los datos del "
                "club antes que la clasificación"
            )
        return int(team.series_ht_id)

    async def _academia_del_equipo(self, uow: UnitOfWork, team_id: int) -> int | None:
        """El id de la cantera de ESTE club, tal y como lo dio `teamdetails`.

        `None` = todavia no se sabe (el club se sincronizo con una version
        anterior de HT Lens); `0` = este club no tiene cantera; cualquier otro
        numero es la suya. La diferencia importa: con `None` se pregunta como
        siempre, y quien avisa de un cruce es la comprobacion del club dueno
        al guardar `youthteamdetails`.
        """
        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)
        return None if team is None else team.ht_youth_team_id

    @staticmethod
    def _edad_en_la_salida(jugador: Any) -> "Age | None":
        """Su edad el día que se fue, si se conoce."""
        if jugador.age_years_at_sale is None or jugador.age_days_at_sale is None:
            return None
        try:
            return Age(jugador.age_years_at_sale, jugador.age_days_at_sale)
        except ValueError:
            return None

    async def _identificador_prestado(
        self,
        uow: UnitOfWork,
        ht_transfer_id: int,
    ) -> int | None:
        """El numero de la transferencia, prestado como identificador.

        Salvaguardia: solo se presta si NADIE lo tiene ya. Los numeros de
        transferencia y los de jugador salen de contadores distintos y podrian
        cruzarse; si eso pasara, atribuir la venta al jugador equivocado seria
        peor que perderla, asi que se pierde.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        duenyo = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_transfer_id)
        )
        if duenyo is not None and not duenyo.ht_player_id_is_transfer:
            return None
        return ht_transfer_id

    if TYPE_CHECKING:
        # Las costuras entre sujetos. Ver el docstring de arriba.
        async def _a_quien_le_subio_el_contador(
            self,
            uow: UnitOfWork,
            team_id: int,
        ) -> list[tuple[Any, datetime]]: ...
        async def _apply_destination_country(self, uow: UnitOfWork, ht_player_id: int) -> bool: ...
        async def _apply_player_enrichment(
            self, uow: UnitOfWork, ht_player_id: int, fetched_at: datetime
        ) -> bool: ...
        async def _apply_transfers_player_purchase(
            self, uow: UnitOfWork, team_id: int, ht_player_id: int
        ) -> bool: ...
        async def _backfill_foreign_match_type(
            self,
            uow: UnitOfWork,
            ht_match_id: int,
            jugado_el: datetime | None = None,
        ) -> None: ...
        async def _best_recent_rating(
            self, ht_team_id: int, ht_player_id: int, matches_to_check: int = 3
        ) -> float | None: ...
        async def _censar_partidos_del_stint(
            self,
            uow: UnitOfWork,
            team_id: int,
            ht_player_id: int,
        ) -> bool: ...
        async def _check_previous_club_bonus(
            self,
            uow: UnitOfWork,
            team_id: int,
            ht_player_id: int,
        ) -> bool: ...
        async def _cuadrar_fichas_prestadas(
            self,
            uow: UnitOfWork,
            team_id: int,
            etapas: list[Any],
            jugadores: dict[int, Any],
        ) -> None: ...
        async def _fetch_last_match_behaviour(
            self,
            uow: UnitOfWork,
            ht_player_id: int,
            ht_match_id: int | None,
            team_id: int,
        ) -> int | None: ...
        async def _fichas_de_los_sin_identificador(
            self,
            uow: UnitOfWork,
            team_id: int,
            movimientos: list[Any],
            jugadores: dict[int, Any],
        ) -> dict[int, int]: ...
        async def _games_played_for_us(
            self,
            ht_team_id: int,
            ht_player_id: int,
            purchased_at: datetime,
            sold_at: datetime,
        ) -> int: ...
        async def _mirar_si_entro_comision(
            self,
            uow: UnitOfWork,
            team_id: int,
        ) -> bool: ...
        async def _misma_ficha_o_la_de_seleccion(
            self,
            payload: dict[str, Any],
            ht_match_id: int,
            jugado_el: datetime | None,
        ) -> dict[str, Any]: ...
        async def _persist_skill_ups(
            self,
            uow: UnitOfWork,
            team_id: int,
            payload: dict[str, Any],
            captured_at: datetime,
            result: SyncResult,
        ) -> None: ...
        async def _reabrir_cierres_por_error(
            self,
            uow: UnitOfWork,
            team_id: int,
        ) -> int: ...
        async def _reconstruir_etapas(self, uow: UnitOfWork, team_id: int) -> int: ...
        async def _vigilar_reventa(
            self,
            uow: UnitOfWork,
            team_id: int,
            ht_player_id: int,
        ) -> bool: ...
        async def pendientes_de_ficha(
            self,
            uow: UnitOfWork,
            team_id: int,
            revisar_desde: datetime | None = None,
        ) -> dict[str, list[int]]: ...
