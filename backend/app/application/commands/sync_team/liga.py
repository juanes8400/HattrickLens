"""Clasificacion y calendario de liga.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    SyncResult,
    _as_change_row,
    trasladar_equipo_reemplazado,
)
from app.domain.engines.composicion_de_liga import (
    Equipo,
    Veredicto,
    cambios_de,
    sin_repetir,
    verificar,
)
from app.domain.engines.sync_diff import diff_standing
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_time import ht_to_utc
from app.infrastructure.db import models as m


def _arreglar_la_foto(foto: list[m.Standing], veredicto: Veredicto) -> int:
    """Pone en la foto guardada al equipo que de verdad ocupa esa plaza.

    POR QUÉ HACE FALTA. La clasificación que se enseña sale de la última foto
    guardada, y una jornada se guarda UNA vez: `_persist_standings` corta con
    `if exists: return`. Un equipo abandonado se reemplaza cuando se reemplaza,
    no en el cambio de jornada, así que entre el reemplazo y la jornada
    siguiente la tabla enseñaba al equipo viejo y no al nuevo. Hasta siete días.

    QUÉ SE CORRIGE, Y NADA MÁS:

    · El REEMPLAZO LIMPIO, uno por uno. Se sabe qué plaza es --la del que se
      fue-- así que se le cambia el id y el nombre. Los puntos y los goles se
      quedan: Hattrick le pasa el expediente de la plaza al sustituto, y esa
      fila describe la plaza, no al club que la ocupaba.
    · El RENOMBRADO. Mismo id, nombre nuevo. Trivial y sin riesgo.

    QUÉ NO SE TOCA, y es la mitad del valor de esto:

    · Una foto incompleta. Con siete equipos de ocho, el «uno que falta» puede
      ser el que no llegó y no el que se fue; `se_arregla_solo` ya lo exige.
    · Dos reemplazos a la vez. No hay forma de saber cuál ocupa el sitio de
      cuál sin preguntar, y adivinar mandaría los puntos al club equivocado.
      Eso se avisa y se queda sin arreglar, que es lo honesto.
    · Las jornadas ANTERIORES. Esas sí las jugó el equipo viejo, y reescribirlas
      sería falsear el histórico. Sólo se corrige la última, que es la que
      representa el AHORA.

    Devuelve cuántas filas se cambiaron.
    """
    if not foto:
        return 0
    por_id = {f.team_ht_id: f for f in foto}
    cambiadas = 0

    if veredicto.se_arregla_solo and veredicto.reemplazo_limpio is not None:
        viejo, nuevo = veredicto.reemplazo_limpio
        fila = por_id.get(viejo.ht_team_id)
        if fila is not None and nuevo.ht_team_id:
            fila.team_ht_id = nuevo.ht_team_id
            fila.team_name = nuevo.nombre
            cambiadas += 1

    for r in veredicto.renombrados:
        fila = por_id.get(r.ht_team_id)
        if fila is not None and fila.team_name != r.ahora:
            fila.team_name = r.ahora
            cambiadas += 1

    return cambiadas


async def _verificar_la_composicion(
    session: Any,
    team_id: int,
    series_ht_id: int,
    season: int,
    payload: dict[str, Any],
    result: SyncResult,
) -> None:
    """Compara los equipos que llegaron con los que teníamos, y lo anota.

    2026-11-07, pedido del usuario: «crea un mecanismo continuo de verificación
    para verificar la composición de la liga».

    CONTRA LA ÚLTIMA JORNADA GUARDADA de esta misma temporada, que es la foto
    más reciente que tenemos de quién está en la serie. No contra la primera: la
    liga cambia dentro de la temporada --un equipo abandonado se reemplaza por
    otro con otro id-- y comparar con la jornada 1 en la jornada 12 anunciaría
    otra vez el reemplazo de la jornada 8 en cada sincronización.

    NI TEMPORADA NI SERIE, NO SE COMPRUEBA NADA. Sin `series_ht_id` no se sabe
    de qué serie hablar, y con `season` en cero --que es lo que se guarda
    cuando todavía no hay `worlddetails`-- la foto guardada y la que llega
    podrían ser de temporadas distintas. Comparar a ciegas daría ocho equipos
    entrando y ocho saliendo cada vez que se sincroniza antes de conocer el
    mundo.

    Y CORRIGE LA FOTO, que es lo que faltaba (2026-11-07, lo vio el usuario:
    «lo de la Liga no funcionó, porque veo un equipo que ya no está y no veo al
    equipo que lo reemplazó»).

    Tenía razón y el fallo era de diseño: esto sólo avisaba. La clasificación
    que se enseña sale de la última foto guardada, y `_persist_standings` corta
    en seco cuando la jornada ya está --`if exists: return`-- así que un
    reemplazo a mitad de semana dejaba el equipo viejo en la tabla hasta la
    jornada siguiente. Hasta siete días con un fantasma en la clasificación y
    sin su sustituto, que es exactamente lo que vio.

    El veredicto es del dominio y se prueba solo. Aquí se lee lo guardado, se le
    pasa, lo que vuelva se anota en Cambios, y además se arregla la foto.
    """
    if not series_ht_id or not season:
        return
    ultima = await session.scalar(
        select(m.Standing.match_round)
        .where(
            m.Standing.series_ht_id == series_ht_id,
            m.Standing.season == season,
        )
        .order_by(m.Standing.match_round.desc())
        .limit(1)
    )
    guardados: list[Equipo] = []
    foto: list[m.Standing] = []
    if ultima is not None:
        foto = list(
            (
                await session.execute(
                    select(m.Standing).where(
                        m.Standing.series_ht_id == series_ht_id,
                        m.Standing.season == season,
                        m.Standing.match_round == ultima,
                    )
                )
            ).scalars()
        )
        guardados = [Equipo(ht_team_id=f.team_ht_id, nombre=f.team_name) for f in foto]
    llegados = [
        Equipo(ht_team_id=int(e.get("ht_team_id", 0) or 0), nombre=str(e.get("name", "") or ""))
        for e in payload.get("teams", [])
    ]
    veredicto = verificar(guardados, llegados)
    # SE CORRIGE ANTES DE AVISAR, y el orden da igual para el resultado pero no
    # para leer esto: lo que importa es que la corrección sale del MISMO
    # veredicto que el aviso, así que nunca se arregla una cosa y se anuncia
    # otra.
    arreglados = _arreglar_la_foto(foto, veredicto)
    if arreglados:
        result.snapshots_written += arreglados
    hallazgos = cambios_de(veredicto)
    if not hallazgos:
        return
    # LO QUE YA SE DIJO, para no decirlo otra vez. Ver `sin_repetir`: la foto
    # guardada no se actualiza hasta la jornada siguiente, así que el mismo
    # hallazgo volvería a salir en cada sincronización mientras tanto.
    #
    # Sólo las de composición y sólo las recientes: el histórico entero de
    # Cambios puede ser largo, y un reemplazo de hace tres temporadas no tiene
    # por qué silenciar el de hoy.
    #
    # Se filtra por `category` y no por el metric: `sync_changes` guarda el
    # metric DENTRO de `detail_json`, no en una columna, y meter un `LIKE`
    # sobre un JSON para ahorrar unas filas no vale lo que cuesta. Las frases
    # de composición no se parecen a las de posición, así que no hay choque.
    ya_dichos = (
        await session.execute(
            select(m.SyncChange.summary)
            .where(
                m.SyncChange.team_id == team_id,
                m.SyncChange.category == "liga",
            )
            .order_by(m.SyncChange.id.desc())
            .limit(60)
        )
    ).scalars()
    for cambio in sin_repetir(hallazgos, list(ya_dichos)):
        result.changes.append(_as_change_row(cambio))


class LigaMixin(BaseDeSync):
    """Clasificacion y calendario de liga."""

    async def _persist_standings(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        ht_team_id: int,
        captured_at: datetime,
        payload: dict[str, Any],
        result: SyncResult,
    ) -> None:
        """Clasificación de la serie: HL-080. Una jornada ya registrada no se
        repite, la tabla completa de una jornada es la unidad append-only,
        no la fila de un equipo."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        # LeagueLevel/MaxLevel (HL-145) son del EQUIPO, no de una jornada
        # se refrescan siempre, aunque esta jornada ya estuviera guardada.
        team = await uow.session.get(m.Team, team_id)
        if team is not None:
            team.league_level = payload.get("league_level", -1)
            team.max_level = payload.get("max_level", -1)

        series_ht_id = payload.get("series_ht_id", 0)
        # CurrentMatchRound de leaguedetails.xml es la jornada que está EN
        # CURSO (o a punto de arrancar), no la última jugada, verificado en
        # vivo: un sync hecho antes de que se juegue ningún partido reporta
        # CurrentMatchRound=1 con `Matches=0` para todos los equipos, y solo
        # tras jugarse esa jornada el valor sube a 2. Guardar el crudo
        # etiquetaría esa foto "sin jugar nada" como si fuera la jornada 1
        # real, y desplazaría todo lo demás un puesto. Restar 1 (con suelo en
        # 0) da "jornadas realmente completadas", que es lo que el resto del
        # sistema espera de `match_round`.
        match_round = max(payload.get("match_round", 0) - 1, 0)
        # 2026-09-13, bug en vivo: justo después de jugarse la jornada 8 un sync
        # recibió los resultados pero CurrentMatchRound aún no había avanzado;
        # la resta daba 7, la 7 ya estaba guardada y la foto nueva se tiraba.
        # Los partidos jugados de cada equipo no dependen de ese contador.
        jugados = [t.get("matches", 0) for t in payload.get("teams", [])]
        if jugados:
            match_round = max(jugados)
        # leaguedetails.xml no trae la temporada; worlddetails sí. Sin
        # sincronizarlo aún, season=0, honesto, no un dato inventado.
        #
        # 2026-08-09, bug real verificado en vivo: cada país tiene su propio
        # número de temporada (Suecia 95, Colombia 83, Grecia 80, todos
        # sincronizados el mismo día) y worlddetails.xml trae TODOS los
        # países en una sola respuesta con el mismo `refreshed_at`. Sin
        # filtrar por país, "la fila más reciente" era básicamente al azar
        # entre esos empates, un fetch en vivo confirmó Colombia en
        # temporada 83, pero `Standing.season` había quedado guardado en 80,
        # 84 e incluso 95 (¡la de Suecia!) en syncs anteriores. Mismo bug y
        # misma corrección que `season_at()` en player_balance.py: filtrar
        # por `Team.ht_league_id` (de teamdetails.xml), el país real de
        # ESTE equipo.
        world = (
            await uow.session.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team is not None and team.ht_league_id is not None
            else None
        )
        season = world.season if world is not None else 0
        # Antes de mirar si la jornada ya estaba: un reemplazo de equipo se
        # tiene que trasladar al calendario aunque la foto no cambie.
        trasladados = await trasladar_equipo_reemplazado(
            uow.session, series_ht_id, payload.get("teams", [])
        )
        if trasladados:
            result.snapshots_written += trasladados

        # LA VERIFICACIÓN, AQUÍ Y NO MÁS ABAJO (2026-11-07, pedido del usuario:
        # «crea un mecanismo continuo de verificación para verificar la
        # composición de la liga»).
        #
        # Va antes del `if exists`, que corta en seco cuando la jornada ya se
        # guardó. Eso es lo que la hace CONTINUA: la composición se comprueba en
        # cada sincronización, no una vez por jornada. Un reemplazo de equipo
        # ocurre cuando ocurre --el 2026-09-13, justo después de la jornada 8--
        # y esperar a la jornada siguiente para notarlo es esperar una semana.
        #
        # Y sólo MIRA. El arreglo del calendario es la línea de arriba, que ya
        # existía; esto dice lo que pasó, incluido lo que ese arreglo no sabe
        # hacer: dos reemplazos a la vez, un renombrado, o una foto a medias.
        # Hasta hoy, en esos tres casos `trasladar_equipo_reemplazado` devolvía
        # 0 y nadie se enteraba.
        await _verificar_la_composicion(uow.session, team_id, series_ht_id, season, payload, result)
        exists = await uow.session.scalar(
            select(m.Standing.id).where(
                m.Standing.series_ht_id == series_ht_id,
                m.Standing.season == season,
                m.Standing.match_round == match_round,
            )
        )
        if exists:
            result.unchanged += 1
            return

        old_standing = await uow.session.scalar(
            select(m.Standing)
            .where(
                m.Standing.series_ht_id == series_ht_id,
                m.Standing.season == season,
                m.Standing.team_ht_id == ht_team_id,
            )
            .order_by(m.Standing.match_round.desc())
            .limit(1)
        )
        old_position = old_standing.position if old_standing is not None else None

        for t in payload.get("teams", []):
            uow.session.add(
                m.Standing(
                    sync_id=sync_id,
                    series_ht_id=series_ht_id,
                    season=season,
                    match_round=match_round,
                    captured_at=captured_at,
                    team_ht_id=t.get("ht_team_id", 0),
                    team_name=t.get("name", ""),
                    position=t.get("position", 0),
                    played=t.get("matches", 0),
                    won=t.get("won", 0),
                    draws=t.get("draws", 0),
                    lost=t.get("lost", 0),
                    goals_for=t.get("goals_for", 0),
                    goals_against=t.get("goals_against", 0),
                    points=t.get("points", 0),
                )
            )
        result.snapshots_written += 1

        own = next((t for t in payload.get("teams", []) if t.get("ht_team_id") == ht_team_id), None)
        if own is not None:
            change = diff_standing(old_position, own.get("position", 0), own.get("name", ""))
            if change:
                result.changes.append(_as_change_row(change))

    async def _persist_league_fixtures(
        self, uow: UnitOfWork, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """Calendario completo de la serie, HL-090 fix.

        A diferencia de `_persist_matches` (que solo ve los partidos del
        equipo sincronizado), aquí llegan también los cruces entre dos
        rivales. Si el partido ya existe (porque `matches` ya lo trajo, o
        de un sync anterior), solo se rellenan `series_ht_id`/`match_round`
        y, 2026-08-08 fix (bug real, no un retraso de CHPP), el marcador
        SI la fila todavía tenía el placeholder "no jugado" (-1): antes,
        una vez creada la fila con -1 la primera vez que se vio el cruce
        sin jugar, un sync posterior nunca volvía a mirar el marcador
        porque `series_ht_id`/`match_round` ya coincidían y el código
        cortaba con `continue`, así un partido entre dos rivales podía
        quedarse "sin jugar" para siempre aunque CHPP ya tuviera el
        resultado real. Un marcador YA confirmado (>= 0) nunca se pisa
        esa fuente la conoce mejor `matches.xml`/`matchdetails.xml`. Si no
        existe, se crea con lo que trae este fichero, marcado como de
        liga."""
        from sqlalchemy import select

        from app.domain.value_objects.ht_constants import MATCH_TYPE_LEAGUE
        from app.infrastructure.db import models as m

        series_ht_id = payload.get("series_ht_id")
        # La temporada que este fichero dice traer. Una serie guarda los
        # partidos de todas las suyas bajo el mismo id, y sin apuntarla los del
        # año pasado se cuentan como de éste en cuanto uno cambia de serie
        # (2026-11-02).
        series_season = payload.get("season")
        for mt in payload.get("matches", []):
            ht_match_id = mt["ht_match_id"]
            row = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == ht_match_id)
            )
            date_str = mt.get("match_date", "")
            played_at = ht_to_utc(date_str) or datetime.now(UTC)
            home_goals = mt.get("home_goals")
            away_goals = mt.get("away_goals")
            if row is None:
                row = m.Match(
                    ht_match_id=ht_match_id,
                    played_at=played_at,
                    match_type=MATCH_TYPE_LEAGUE,
                    status="FINISHED" if home_goals is not None else "UPCOMING",
                    home_team_ht_id=mt.get("home_team_id", 0),
                    away_team_ht_id=mt.get("away_team_id", 0),
                    home_team_name=mt.get("home_team_name", ""),
                    away_team_name=mt.get("away_team_name", ""),
                    home_goals=home_goals if home_goals is not None else -1,
                    away_goals=away_goals if away_goals is not None else -1,
                    series_season=series_season,
                )
                uow.session.add(row)
                result.snapshots_written += 1
                continue
            changed = False
            if row.series_ht_id != series_ht_id or row.match_round != mt.get("match_round"):
                row.series_ht_id = series_ht_id
                row.match_round = mt.get("match_round")
                changed = True
            # La temporada se rellena aunque lo demás ya cuadre: es lo que pone
            # al día lo guardado antes de que existiera esta columna.
            if series_season is not None and row.series_season != series_season:
                row.series_season = series_season
                changed = True
            # Los equipos, los que dice Hattrick HOY, jugado o no. 2026-09-13:
            # Kivaré reemplazó a etbenianos1 y Hattrick le atribuye también la
            # jornada 8 ya jugada; el calendario guardado arrastraba el nombre
            # y el id viejos desde el primer sync y nunca los revisaba.
            for campo_id, campo_nombre, clave in (
                ("home_team_ht_id", "home_team_name", "home"),
                ("away_team_ht_id", "away_team_name", "away"),
            ):
                nuevo_id = mt.get(f"{clave}_team_id")
                nuevo_nombre = mt.get(f"{clave}_team_name")
                if nuevo_id and getattr(row, campo_id) != nuevo_id:
                    setattr(row, campo_id, nuevo_id)
                    changed = True
                if nuevo_nombre and getattr(row, campo_nombre) != nuevo_nombre:
                    setattr(row, campo_nombre, nuevo_nombre)
                    changed = True
            if row.home_goals < 0 and home_goals is not None and away_goals is not None:
                row.home_goals = home_goals
                row.away_goals = away_goals
                row.status = "FINISHED"
                row.played_at = played_at
                changed = True
            if changed:
                result.snapshots_written += 1
            else:
                result.unchanged += 1
