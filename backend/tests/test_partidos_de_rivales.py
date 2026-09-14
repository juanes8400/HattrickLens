"""Guardar los partidos de los rivales para no repedirlos.

2026-09-09, pedido del usuario: «me dice que ya llamé muchísimas veces la info
de rivales y sus partidos, y es verdad. En Sync, vas a cargar los 5 partidos
oficiales de cada contrincante de Liga de una, guárdalos para que no toque
volverlos a llamar y guardas el último eliminando el más antiguo».

Lo que se prueba aquí es lo que el usuario puede notar: cuántas llamadas se
hacen, cuántas se dejan de hacer la segunda vez, y que la ventana no crece.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.partidos_de_rivales import (
    PARTIDOS_GUARDADOS_POR_RIVAL,
    alineacion_de,
    guardar_partidos_de_rivales,
    partidos_guardados,
    ratings_de,
)
from app.infrastructure.db import models as m

RIVAL = 500001
OTRO = 500002


class CHPPFalso:
    """Un Hattrick de mentira que APUNTA cada llamada.

    El contador es el objeto de la prueba: lo que se quiere demostrar no es
    que los datos lleguen --eso sería trivial-- sino que la segunda vez NO se
    piden.
    """

    def __init__(self, partidos: int = 7) -> None:
        self.llamadas: list[tuple[str, Any]] = []
        self.partidos = partidos

    async def fetch(self, file: str, version: str = "", **params: Any) -> dict[str, Any]:
        self.llamadas.append((file, params))
        if file == "matches":
            equipo = params["teamID"]
            base = datetime(2026, 7, 1, 20, tzinfo=UTC)
            return {
                "matches": [
                    {
                        "ht_match_id": equipo * 100 + i,
                        "match_type": 1,
                        "match_date": (base + timedelta(days=7 * i)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "status": "FINISHED",
                        "home_team_id": equipo,
                        "away_team_id": 999,
                        "home_team_name": f"Equipo {equipo}",
                        "away_team_name": "Rival de turno",
                        "home_goals": i,
                        "away_goals": 0,
                    }
                    for i in range(self.partidos)
                ]
            }
        if file == "matchdetails":
            equipo = params["matchID"] // 100
            return {
                "home": {
                    "team_id": equipo,
                    "tactic_type": 4,
                    "tactic_skill": 11,
                    "formation": "4-4-2",
                    "ratings": {
                        "midfield": 20,
                        "left_def": 21,
                        "central_def": 22,
                        "right_def": 23,
                        "left_att": 24,
                        "central_att": 25,
                        "right_att": 26,
                        "set_pieces_def": 27,
                        "set_pieces_att": 28,
                    },
                },
                "away": {"team_id": 999, "ratings": {}},
            }
        if file == "matchlineup":
            return {
                "players": [
                    {"ht_player_id": 1, "name": "Uno", "position_code": 5},
                    {"ht_player_id": 2, "name": "Dos", "position_code": 7},
                ]
            }
        return {}

    def cuantas(self, file: str) -> int:
        return sum(1 for f, _ in self.llamadas if f == file)


async def _sesion() -> async_sessionmaker:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


def test_guarda_cinco_por_rival_y_no_mas() -> None:
    """El rival tiene siete partidos jugados; se guardan los CINCO últimos.

    No es un archivo histórico: es la muestra que la ficha mira, y un partido
    de hace tres meses describe a un equipo que ya no existe.
    """

    async def go() -> None:
        factory = await _sesion()
        chpp = CHPPFalso(partidos=7)
        async with factory() as s:
            resumen = await guardar_partidos_de_rivales(s, chpp, {RIVAL}, "2.8", "3.1")
            await s.commit()

            cuantos = await s.scalar(
                select(func.count()).select_from(m.RivalMatch).where(
                    m.RivalMatch.team_ht_id == RIVAL
                )
            )
            assert cuantos == PARTIDOS_GUARDADOS_POR_RIVAL
            assert resumen.partidos_nuevos == PARTIDOS_GUARDADOS_POR_RIVAL

            # Los cinco ÚLTIMOS, no los cinco primeros: los partidos 2..6.
            guardados = await partidos_guardados(s, RIVAL)
            assert [f.ht_match_id for f in guardados] == [
                RIVAL * 100 + i for i in range(2, 7)
            ]
            # Y en orden ascendente, que es lo que necesita «último partido».
            assert guardados[-1].played_at > guardados[0].played_at

    asyncio.run(go())


def test_la_segunda_vez_no_pide_ningun_partido() -> None:
    """La razón de existir de todo esto.

    Un partido terminado no cambia nunca. Si la segunda pasada volviera a
    pedirlos, guardar no ahorraría nada: sólo habría movido el gasto del
    momento de mirar al de sincronizar.
    """

    async def go() -> None:
        factory = await _sesion()
        chpp = CHPPFalso(partidos=5)
        async with factory() as s:
            await guardar_partidos_de_rivales(s, chpp, {RIVAL}, "2.8", "3.1")
            await s.commit()
        primera = (chpp.cuantas("matchdetails"), chpp.cuantas("matchlineup"))
        assert primera == (5, 5)

        async with factory() as s:
            resumen = await guardar_partidos_de_rivales(s, chpp, {RIVAL}, "2.8", "3.1")
            await s.commit()

        # El calendario sí se vuelve a pedir --hay que saber si hay jornada
        # nueva-- pero ni un detalle ni una alineación más.
        assert chpp.cuantas("matches") == 2
        assert chpp.cuantas("matchdetails") == 5
        assert chpp.cuantas("matchlineup") == 5
        assert resumen.partidos_nuevos == 0
        assert resumen.partidos_ya_estaban == 5

    asyncio.run(go())


def test_una_jornada_nueva_entra_y_el_mas_viejo_sale() -> None:
    """«Guardas el último eliminando el más antiguo», textual del usuario."""

    async def go() -> None:
        factory = await _sesion()
        chpp = CHPPFalso(partidos=5)
        async with factory() as s:
            await guardar_partidos_de_rivales(s, chpp, {RIVAL}, "2.8", "3.1")
            await s.commit()
            antes = [f.ht_match_id for f in await partidos_guardados(s, RIVAL)]

        # Se juega una jornada más.
        chpp.partidos = 6
        async with factory() as s:
            resumen = await guardar_partidos_de_rivales(s, chpp, {RIVAL}, "2.8", "3.1")
            await s.commit()
            despues = [f.ht_match_id for f in await partidos_guardados(s, RIVAL)]

            total = await s.scalar(
                select(func.count()).select_from(m.RivalMatch).where(
                    m.RivalMatch.team_ht_id == RIVAL
                )
            )

        assert resumen.partidos_nuevos == 1
        assert resumen.borrados_por_antiguos == 1
        # Sigue habiendo cinco: entró el nuevo y salió el más viejo.
        assert total == PARTIDOS_GUARDADOS_POR_RIVAL
        assert despues[-1] == RIVAL * 100 + 5
        assert antes[0] not in despues

    asyncio.run(go())


def test_cada_rival_guarda_su_propio_lado() -> None:
    """Dos contrincantes de liga, dos juegos de cinco filas, sin pisarse."""

    async def go() -> None:
        factory = await _sesion()
        chpp = CHPPFalso(partidos=5)
        async with factory() as s:
            await guardar_partidos_de_rivales(s, chpp, {RIVAL, OTRO}, "2.8", "3.1")
            await s.commit()

            assert len(await partidos_guardados(s, RIVAL)) == 5
            assert len(await partidos_guardados(s, OTRO)) == 5
            uno = (await partidos_guardados(s, RIVAL))[0]
            # Lo guardado es el lado DE ESE rival, con sus nueve ratings.
            assert ratings_de(uno) == {
                "midfield": 20,
                "left_def": 21,
                "central_def": 22,
                "right_def": 23,
                "left_att": 24,
                "central_att": 25,
                "right_att": 26,
                "sp_def": 27,
                "sp_att": 28,
            }
            assert uno.tactic_type == 4
            assert uno.formation == "4-4-2"
            assert [p["name"] for p in alineacion_de(uno)] == ["Uno", "Dos"]

    asyncio.run(go())


def test_una_lectura_incompleta_no_se_usa() -> None:
    """Viene o no viene: media lectura no es una lectura con ceros.

    Es la misma regla que rige la ficha de rival. Un rating ausente leído como
    cero convierte la proporción `A/(A+B)` en 0,000, o sea en afirmar que el
    rival gana ese duelo entero.
    """
    fila = m.RivalMatch(
        team_ht_id=RIVAL,
        ht_match_id=1,
        match_type=1,
        played_at=datetime(2026, 7, 1, tzinfo=UTC),
        home_team_ht_id=RIVAL,
        away_team_ht_id=999,
        home_team_name="A",
        away_team_name="B",
        midfield=20,
        left_def=21,
        central_def=22,
        right_def=23,
        left_att=24,
        central_att=25,
        right_att=26,
        set_pieces_def=None,  # la que falta
        set_pieces_att=28,
        lineup_json="[]",
        captured_at=datetime.now(UTC),
    )
    assert ratings_de(fila) is None


def test_una_alineacion_ilegible_no_tumba_la_ficha() -> None:
    """Un JSON roto es un partido del que no se sabe quién jugó, no un error."""
    fila = m.RivalMatch(
        team_ht_id=RIVAL,
        ht_match_id=1,
        match_type=1,
        played_at=datetime(2026, 7, 1, tzinfo=UTC),
        home_team_ht_id=RIVAL,
        away_team_ht_id=999,
        home_team_name="A",
        away_team_name="B",
        lineup_json="{esto no es json",
        captured_at=datetime.now(UTC),
    )
    assert alineacion_de(fila) == []
    fila.lineup_json = json.dumps({"no": "es una lista"})
    assert alineacion_de(fila) == []


def test_un_rival_caido_no_tumba_la_precarga() -> None:
    """Los partidos de un equipo ajeno son una comodidad, no estado del club."""

    class Caido(CHPPFalso):
        async def fetch(self, file: str, version: str = "", **params: Any) -> dict[str, Any]:
            if file == "matches" and params.get("teamID") == RIVAL:
                raise RuntimeError("Hattrick no contesta")
            return await super().fetch(file, version, **params)

    async def go() -> None:
        factory = await _sesion()
        chpp = Caido(partidos=5)
        async with factory() as s:
            resumen = await guardar_partidos_de_rivales(s, chpp, {RIVAL, OTRO}, "2.8", "3.1")
            await s.commit()
            # El que se cayó se anota; el otro se guarda igual.
            assert len(resumen.errores) == 1
            assert str(RIVAL) in resumen.errores[0]
            assert len(await partidos_guardados(s, RIVAL)) == 0
            assert len(await partidos_guardados(s, OTRO)) == 5

    asyncio.run(go())


def _partido(equipo: int, i: int, tipo: int) -> dict[str, Any]:
    """Una cabecera como la del calendario, con un día por partido."""
    base = datetime(2026, 7, 1, 20, tzinfo=UTC)
    return {
        "ht_match_id": equipo * 1000 + i,
        "match_type": tipo,
        "match_date": (base + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S"),
        "home_team_id": equipo,
        "away_team_id": 999,
        "home_team_name": f"Equipo {equipo}",
        "away_team_name": "Rival de turno",
        "home_goals": 2,
        "away_goals": 1,
    }


def _lado(equipo: int) -> dict[str, Any]:
    return {
        "team_id": equipo,
        "tactic_type": 0,
        "tactic_skill": 0,
        "formation": "5-5-0",
        "ratings": {
            "midfield": 10,
            "left_def": 10,
            "central_def": 10,
            "right_def": 10,
            "left_att": 10,
            "central_att": 10,
            "right_att": 10,
            "set_pieces_def": 10,
            "set_pieces_att": 10,
        },
    }


def test_la_ficha_guarda_lo_que_acaba_de_pedir() -> None:
    """2026-09-10: los rivales que el sync no precarga --amistosos, IDs a
    mano, o una jornada jugada después del último sync-- se guardan desde la
    primera vez que la ficha los pide."""
    from app.application.commands.partidos_de_rivales import guardar_lo_visto

    async def go() -> None:
        factory = await _sesion()
        partidos = [_partido(RIVAL, i, 9) for i in range(3)]
        alineaciones = {p["ht_match_id"]: [{"ht_player_id": 1, "name": "Uno"}] for p in partidos}
        lados = {p["ht_match_id"]: _lado(RIVAL) for p in partidos}
        async with factory() as s:
            assert await guardar_lo_visto(s, RIVAL, partidos, alineaciones, lados) == 3
            await s.commit()
            guardados = await partidos_guardados(s, RIVAL, limite=None)
            assert [f.ht_match_id for f in guardados] == [p["ht_match_id"] for p in partidos]
            # El marcador entero, para «Último partido».
            assert guardados[-1].home_team_name == f"Equipo {RIVAL}"
            assert (guardados[-1].home_goals, guardados[-1].away_goals) == (2, 1)

    asyncio.run(go())


def test_sin_alineacion_o_sin_detalle_no_se_guarda_media_fila() -> None:
    """Media fila obligaría a volver a pedir la otra mitad en la siguiente
    visita: no ahorraría nada."""
    from app.application.commands.partidos_de_rivales import guardar_lo_visto

    async def go() -> None:
        factory = await _sesion()
        solo_alineacion, solo_detalle = _partido(RIVAL, 0, 9), _partido(RIVAL, 1, 9)
        async with factory() as s:
            n = await guardar_lo_visto(
                s,
                RIVAL,
                [solo_alineacion, solo_detalle],
                {solo_alineacion["ht_match_id"]: []},
                {solo_detalle["ht_match_id"]: _lado(RIVAL)},
            )
            await s.commit()
            assert n == 0
            assert await partidos_guardados(s, RIVAL, limite=None) == []

    asyncio.run(go())


def test_guardar_dos_veces_lo_mismo_no_revienta_ni_duplica() -> None:
    """Dos pestañas abiertas sobre el mismo rival guardan el mismo partido a
    la vez. La segunda no puede tumbar la ficha contra la clave única."""
    from app.application.commands.partidos_de_rivales import guardar_lo_visto

    async def go() -> None:
        factory = await _sesion()
        partidos = [_partido(RIVAL, i, 9) for i in range(2)]
        alineaciones = {p["ht_match_id"]: [] for p in partidos}
        lados = {p["ht_match_id"]: _lado(RIVAL) for p in partidos}
        async with factory() as s:
            await guardar_lo_visto(s, RIVAL, partidos, alineaciones, lados)
            await guardar_lo_visto(s, RIVAL, partidos, alineaciones, lados)
            await s.commit()
            assert len(await partidos_guardados(s, RIVAL, limite=None)) == 2

    asyncio.run(go())


def test_la_ventana_es_de_cinco_por_clase() -> None:
    """Cinco oficiales y cinco amistosos, cada clase con su recorte.

    Con un solo recorte de cinco en total, guardar los amistosos de un rival
    echaba a sus oficiales, y la siguiente visita a los oficiales los volvía a
    descargar enteros.
    """
    from app.application.commands.partidos_de_rivales import guardar_lo_visto

    async def go() -> None:
        factory = await _sesion()
        oficiales = [_partido(RIVAL, i, 1) for i in range(7)]
        amistosos = [_partido(RIVAL, 100 + i, 9) for i in range(7)]
        async with factory() as s:
            for grupo in (oficiales, amistosos):
                await guardar_lo_visto(
                    s,
                    RIVAL,
                    grupo,
                    {p["ht_match_id"]: [] for p in grupo},
                    {p["ht_match_id"]: _lado(RIVAL) for p in grupo},
                )
            await s.commit()
            filas = await partidos_guardados(s, RIVAL, limite=None)

        de_liga = [f.ht_match_id for f in filas if f.match_type == 1]
        de_amistoso = [f.ht_match_id for f in filas if f.match_type == 9]
        # Cinco de cada, y los cinco MÁS RECIENTES de cada uno.
        assert de_liga == [p["ht_match_id"] for p in oficiales[-5:]]
        assert de_amistoso == [p["ht_match_id"] for p in amistosos[-5:]]

    asyncio.run(go())
