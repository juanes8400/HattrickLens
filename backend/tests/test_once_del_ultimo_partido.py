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

#: La orden individual de cada plaza: el delantero jugo ofensivo (1).
BEHAVIOURS = (0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1)


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


def test_de_los_viejos_solo_se_pide_el_ultimo_OFICIAL() -> None:
    """Un club con anos de historia no puede disparar cien llamadas.

    El corte por fecha es lo que hace que esto termine: lo que queda por pedir
    son como mucho unos pocos partidos recientes, no el archivo entero. Pero el
    ultimo OFICIAL se pide siempre, tenga la edad que tenga, porque es el que
    enseña Equipo como «tu ultima formacion oficial».

    2026-09-28, senalado en la revision de la PR #4: antes se pedia el mas
    reciente A SECAS. Con tres amistosos o escaleras por delante, la
    sincronizacion gastaba su presupuesto entero en ellos y el partido que de
    verdad se enseña no llegaba a pedirse nunca. Aqui el amistoso es tres dias
    MAS NUEVO que el de liga, y aun asi gana el de liga.
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
    # El de liga, aunque el amistoso sea posterior.
    assert [c["matchID"] for c in llamadas] == [LIGA]


async def _con_alineacion_guardada(quitar: int = 0):
    """El partido con su once real guardado, y `quitar` titulares fuera del club."""
    factory, team_id = await _escenario()
    async with factory() as s:
        jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
        titulares = jugadores[: len(PUESTOS)]
        once = [
            {"ht_player_id": j.ht_player_id, "role_id": rol, "behaviour": beh}
            for j, rol, beh in zip(titulares, PUESTOS, BEHAVIOURS, strict=True)
        ]
        partido = await s.scalar(select(m.Match).where(m.Match.ht_match_id == LIGA))
        partido.played_lineup_json = json.dumps(once)
        # Los ultimos de la lista se van del club: ya no estan en la plantilla.
        for j in titulares[len(PUESTOS) - quitar :] if quitar else []:
            await s.delete(await s.scalar(select(m.Player).where(m.Player.id == j.id)))
        await s.commit()
    return factory, team_id


def test_la_formacion_sale_del_partido_aunque_falte_un_titular() -> None:
    """Vender a un delantero no convierte un 3-5-2 en un 3-5-0.

    2026-09-27, pedido del usuario: la formacion es un hecho de esa tarde. Lo
    que cambia es quien puede ocuparla hoy, y esa plaza se rellena.
    """

    async def caso(quitar):
        factory, team_id = await _con_alineacion_guardada(quitar=quitar)
        return await _once_de(factory, team_id)

    entero = asyncio.run(caso(0))
    assert entero.formation == "5-4-1"
    assert entero.lineup_players == 11
    assert entero.lineup_replacements == 0

    # Se va el delantero (el ultimo de PUESTOS, el 111).
    cojo = asyncio.run(caso(1))
    assert cojo.formation == "5-4-1", "la formacion del partido no cambia"
    assert cojo.lineup_players == 11, "la plaza se rellena con la plantilla de hoy"
    assert cojo.lineup_replacements == 1


def test_el_que_entra_hereda_la_orden_individual_de_la_plaza() -> None:
    """Si ese delantero jugo ofensivo, la plaza es de delantero ofensivo.

    Lo que mide los sectores es la orden de la PLAZA, no la del jugador: el
    once que se enseña es el del partido con otro nombre en esa casilla.
    """

    async def caso():
        factory, team_id = await _con_alineacion_guardada(quitar=1)
        r = await _once_de(factory, team_id)
        return [(p.position, p.name) for p in r.players if p.in_lineup]

    once = asyncio.run(caso())
    assert len(once) == 11
    assert sum(1 for puesto, _ in once if puesto == "DEL") == 1


def test_el_pronostico_de_un_partido_es_de_un_club_y_no_de_los_dos() -> None:
    """2026-09-28, senalado en la revision de la PR #4.

    Un partido tiene dos lados y los dos pueden estar conectados a HT Lens: la
    misma cuenta con sus dos clubes, o dos managers distintos. El pronostico NO
    es el mismo para los dos, porque el motor de zonas usa la alineacion que
    ESE manager envio. Si la fila fuera solo del partido, el segundo en abrir
    Liga pisaria la del primero, y despues del partido su parte le enseñaria
    una terna que nunca vio. Que es lo contrario de para lo que existe.
    """

    async def caso():
        from datetime import UTC, datetime

        from app.application.queries.league import _guardar_lo_dicho
        from app.infrastructure.db.session import SessionLocal

        del SessionLocal  # solo para que quede claro cual se usa: la de league
        factory, team_id = await _escenario()
        async with factory() as s:
            otro = m.Team(ht_team_id=600001, name="Deportivo Uno")
            s.add(otro)
            await s.commit()
            otro_id = otro.id

        # `_guardar_lo_dicho` abre su propia sesion a proposito (un commit en
        # la del lector caduca los objetos que todavia esta usando), asi que
        # aqui se escribe igual que ella, contra la misma base.
        import app.application.queries.league as L

        async def escribir(team, home_win):
            async with factory() as s:
                fila = await s.scalar(
                    select(m.MatchPrediction).where(
                        m.MatchPrediction.ht_match_id == LIGA,
                        m.MatchPrediction.team_id == team,
                    )
                )
                valores = dict(
                    home_win=home_win,
                    draw=0.25,
                    away_win=round(1 - home_win - 0.25, 4),
                    expected_home_goals=1.5,
                    expected_away_goals=1.0,
                    most_likely_score="1-1",
                    source="zonas",
                    engine=L.VERSION_DEL_MOTOR,
                    computed_at=datetime.now(UTC),
                )
                if fila is None:
                    s.add(m.MatchPrediction(ht_match_id=LIGA, team_id=team, **valores))
                else:
                    for k, v in valores.items():
                        setattr(fila, k, v)
                await s.commit()

        # Los dos clubes abren Liga y cada uno dice lo suyo del MISMO partido.
        await escribir(team_id, 0.60)
        await escribir(otro_id, 0.20)

        async with factory() as s:
            filas = (await s.execute(select(m.MatchPrediction))).scalars().all()
        return {f.team_id: f.home_win for f in filas}, team_id, otro_id

    por_club, mio, suyo = asyncio.run(caso())
    assert len(por_club) == 2, "cada club guarda lo SUYO, no se pisan"
    assert por_club[mio] == 0.60
    assert por_club[suyo] == 0.20
