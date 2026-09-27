"""El once del ultimo partido sale del PARTIDO, no de la ficha de cada jugador.

2026-09-27, caso concreto del usuario: el partido 770393948 del FC Villainy
salia en Equipo con ocho jugadores y una formacion «3-5-0», que no existe.

La alineacion enviada (`submitted_lineup_json`) solo se captura mientras el
partido sigue PROXIMO y con ordenes dadas. Si nadie sincronizo en esa ventana
--lo normal en un segundo equipo-- ese partido se queda sin ella para siempre,
y el once salia de `player_snapshots.last_match_*`, que guarda el ULTIMO
partido de cada jugador y se pisa en cada sync. Basta un amistoso despues para
que media plantilla deje de apuntar al partido de liga.

`player_match_ratings` es la misma informacion guardada append-only, una fila
por (jugador, partido): lo capturado una vez ya no se pisa.
"""

import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.application.queries.habilidades import HabilidadesQueryService
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

LIGA = 1_000_001
AMISTOSO = 1_000_002
JUGADO = datetime(2026, 3, 1, 21, 40, tzinfo=UTC)

#: Un 5-4-1: portero, dos laterales, tres centrales, dos extremos, dos
#: mediocentros y un delantero.
PUESTOS = (100, 101, 105, 102, 103, 104, 106, 110, 107, 108, 111)


async def _escenario():
    """La liga jugada, sus fichas guardadas, y un amistoso despues encima."""
    factory, team_id = await seeded_session()
    async with factory() as s:
        s.add(
            m.Match(
                ht_match_id=LIGA,
                played_at=JUGADO,
                match_type=1,
                status="FINISHED",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=600001,
                home_team_name="Pulgas Arrechas",
                away_team_name="Deportivo Uno",
                home_goals=2,
                away_goals=1,
                match_round=5,
            )
        )
        s.add(
            m.Match(
                ht_match_id=AMISTOSO,
                played_at=datetime(2026, 3, 4, 21, 40, tzinfo=UTC),
                match_type=4,
                status="FINISHED",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=600002,
                home_team_name="Pulgas Arrechas",
                away_team_name="Atletico Dos",
                home_goals=0,
                away_goals=0,
            )
        )
        jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
        once = jugadores[: len(PUESTOS)]
        for jugador, puesto in zip(once, PUESTOS, strict=True):
            s.add(
                m.PlayerMatchRating(
                    player_id=jugador.id,
                    ht_match_id=LIGA,
                    position_code=puesto,
                    played_minutes=90,
                    rating=5.0,
                    captured_at=JUGADO,
                )
            )
        # Las fichas: solo tres siguen apuntando a la liga. Los otros ocho
        # jugaron el amistoso del sabado y sus `last_match_*` hablan de ese.
        for i, jugador in enumerate(once):
            foto = await s.scalar(
                select(m.PlayerSnapshot).where(m.PlayerSnapshot.player_id == jugador.id)
            )
            de_la_liga = i < 3
            foto.last_match_ht_id = LIGA if de_la_liga else AMISTOSO
            foto.last_match_position_code = PUESTOS[i] if de_la_liga else 114
            foto.last_match_played_minutes = 90
        await s.commit()
    return factory, team_id


async def _once_de(factory, team_id):
    async with factory() as s:
        return await HabilidadesQueryService(s).get(team_id)


def test_el_once_sobrevive_a_un_amistoso_posterior() -> None:
    async def caso():
        factory, team_id = await _escenario()
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.lineup_players == 11
    assert r.formation == "5-4-1"
    assert r.lineup_source == "partido"


def test_sin_las_fichas_del_partido_el_once_queda_corto_y_no_se_inventa_formacion() -> None:
    """El estado ANTERIOR al arreglo, para que se vea que no se tapa solo.

    Sin `player_match_ratings` no hay de donde sacar a los ocho que jugaron el
    amistoso, y el once se queda en tres. Lo que ya no pasa es que esos tres se
    presenten como una formacion.
    """

    async def caso():
        factory, team_id = await _escenario()
        async with factory() as s:
            await s.execute(delete(m.PlayerMatchRating).where(m.PlayerMatchRating.ht_match_id == LIGA))
            await s.commit()
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.lineup_players == 3
    assert r.formation is None
    assert r.lineup_source == "fichas"


def test_el_once_dice_de_que_partido_salio() -> None:
    """2026-09-27, pedido del usuario: la fecha sola no identifica el partido."""

    async def caso():
        factory, team_id = await _escenario()
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.last_match_date == "2026-03-01"
    assert r.last_match_opponent == "Deportivo Uno"
    assert r.last_match_score == "2-1"
    assert r.last_match_is_home is True
    assert r.last_match_competition


class _CHPPConAlineacion:
    """Hattrick devolviendo `matchlineup.xml` v2.1 de un partido ya jugado.

    Se devuelve el diccionario YA PARSEADO, que es lo que entrega `fetch`: lo
    que se prueba aqui es que el sync se quede con el once inicial, no el
    parser de XML, que tiene sus propias pruebas.

    EL `<Lineup>` QUE SE SIMULA ES EL DE VERDAD, con la trampa incluida. En la
    version 2.1 es el estado FINAL del partido, asi que al titular sustituido
    le quita su puesto --se lo queda el suplente que entro-- y de el solo deja
    su fila de papel especial (capitan, balon parado). Visto en vivo en el
    matchID 770453142: el lateral del 101 aparecia con RoleID 19. Un doble que
    no reprodujera eso habria dado por buena la primera version de este
    arreglo, que cruzaba `<Lineup>` con la lista de titulares.
    """

    def __init__(self, titulares: list[int], entraron: list[int]) -> None:
        self.titulares = titulares
        self.entraron = entraron
        self.llamadas: list[dict] = []

    async def fetch(self, file: str, **kw):
        self.llamadas.append({"file": file, **kw})
        if file != "matchlineup":
            raise AssertionError(f"no deberia pedir {file}")
        sustituido = self.titulares[1] if self.entraron else None
        final = [
            {"ht_player_id": pid, "role_id": rol, "behaviour": 0}
            for pid, rol in zip(self.titulares, PUESTOS, strict=True)
            if pid != sustituido
        ]
        # El suplente entra y ocupa el puesto del que salio.
        final += [
            {"ht_player_id": pid, "role_id": PUESTOS[1], "behaviour": 0} for pid in self.entraron
        ]
        # Y del sustituido solo queda su papel especial.
        if sustituido is not None:
            final.append({"ht_player_id": sustituido, "role_id": 19, "behaviour": 0})
        return {
            "ht_match_id": LIGA,
            "ht_team_id": HT_TEAM_ID,
            "players": final,
            "starting_lineup": list(self.titulares),
            # Con su fila de balon parado repetida, como viene de verdad:
            # doce filas para once jugadores.
            "starting_players": [
                {"ht_player_id": pid, "role_id": rol, "behaviour": 0}
                for pid, rol in zip(self.titulares, PUESTOS, strict=True)
            ]
            + [{"ht_player_id": self.titulares[6], "role_id": 18, "behaviour": 0}],
            "substitutions": [],
        }


async def _pedir_alineacion(factory, chpp):
    from app.application.commands.sync_team import SyncResult, SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), chpp)
    async with SqlAlchemyUnitOfWork(factory) as uow:
        await handler._sync_alineaciones_jugadas(
            uow, HT_TEAM_ID, datetime(2026, 3, 5, tzinfo=UTC), SyncResult(sync_id=1, status="ok")
        )
        await uow.commit()


def test_se_guarda_el_once_inicial_con_el_puesto_en_el_que_empezo() -> None:
    """Quien entro de cambio no es titular, y al que salio no se le pierde el puesto."""

    async def caso():
        factory, team_id = await _escenario()
        async with factory() as s:
            jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
            titulares = [j.ht_player_id for j in jugadores[: len(PUESTOS)]]
            suplente = jugadores[len(PUESTOS)].ht_player_id
        await _pedir_alineacion(factory, _CHPPConAlineacion(titulares, [suplente]))
        async with factory() as s:
            partido = await s.scalar(select(m.Match).where(m.Match.ht_match_id == LIGA))
            guardado = json.loads(partido.played_lineup_json)
        return guardado, titulares, suplente

    guardado, titulares, suplente = asyncio.run(caso())
    assert len(guardado) == 11
    assert [j["ht_player_id"] for j in guardado] == titulares
    assert suplente not in {j["ht_player_id"] for j in guardado}
    # Y con su puesto de salida, no con el papel especial que `<Lineup>` le
    # dejaba al titular sustituido.
    assert [j["role_id"] for j in guardado] == list(PUESTOS)


def test_con_la_alineacion_de_hattrick_el_once_ya_no_depende_de_las_fichas() -> None:
    """El arreglo de fondo: ni un amistoso posterior ni la falta de ordenes."""

    async def caso():
        factory, team_id = await _escenario()
        async with factory() as s:
            # Se borran las fichas del partido: ya no hacen falta.
            await s.execute(
                delete(m.PlayerMatchRating).where(m.PlayerMatchRating.ht_match_id == LIGA)
            )
            jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
            titulares = [j.ht_player_id for j in jugadores[: len(PUESTOS)]]
            await s.commit()
        await _pedir_alineacion(factory, _CHPPConAlineacion(titulares, []))
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.lineup_players == 11
    assert r.formation == "5-4-1"
    assert r.lineup_source == "hattrick"


def test_un_partido_ya_guardado_no_se_vuelve_a_pedir() -> None:
    """Un partido jugado no cambia: se pide UNA vez y ya."""

    async def caso():
        factory, _ = await _escenario()
        async with factory() as s:
            jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
            titulares = [j.ht_player_id for j in jugadores[: len(PUESTOS)]]
        chpp = _CHPPConAlineacion(titulares, [])
        await _pedir_alineacion(factory, chpp)
        primera = len(chpp.llamadas)
        await _pedir_alineacion(factory, chpp)
        return primera, [c["matchID"] for c in chpp.llamadas]

    primera, pedidos = asyncio.run(caso())
    # El amistoso tambien esta jugado y tambien se rescata, asi que la primera
    # pasada pide los dos. La segunda no pide ninguno.
    assert LIGA in pedidos
    assert len(pedidos) == primera


def test_de_los_viejos_solo_se_pide_el_ultimo() -> None:
    """Un club con anos de historia no puede disparar cien llamadas.

    El corte por fecha es lo que hace que esto termine: lo que queda por pedir
    son como mucho unos pocos partidos recientes, no el archivo entero. Pero el
    MAS RECIENTE se pide siempre, tenga la edad que tenga, porque es el que
    enseña Equipo y dejarlo fuera por viejo seria dejar rota justo la pantalla
    que motivo todo esto.
    """

    async def caso():
        from app.application.commands.sync_team import SyncResult, SyncTeamHandler
        from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

        factory, _ = await _escenario()
        async with factory() as s:
            jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
            titulares = [j.ht_player_id for j in jugadores[: len(PUESTOS)]]
        chpp = _CHPPConAlineacion(titulares, [])
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), chpp)
        # Un ano despues: los dos partidos quedan fuera de la ventana.
        async with SqlAlchemyUnitOfWork(factory) as uow:
            await handler._sync_alineaciones_jugadas(
                uow,
                HT_TEAM_ID,
                datetime(2027, 3, 5, tzinfo=UTC),
                SyncResult(sync_id=1, status="ok"),
            )
            await uow.commit()
        return chpp.llamadas

    llamadas = asyncio.run(caso())
    # Solo el mas reciente de los dos, que es el amistoso del 4 de marzo.
    assert [c["matchID"] for c in llamadas] == [AMISTOSO]
