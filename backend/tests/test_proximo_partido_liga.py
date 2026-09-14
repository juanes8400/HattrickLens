"""El próximo partido del Resumen de Liga: una alineación concreta por lado.

2026-09-12, pedido del usuario: «la última alineación para el rival, y la
enviada (o si no, la última) para nosotros», y que la pantalla deje claro cuál
se toma y por qué. Hasta ese día el panel usaba el resumen del selector de
Proyección --la mediana, casi siempre-- para los dos lados.

Lo que se fija aquí es el contrato: qué alineación entra de cada lado, que la
táctica viaja con ella, que unas órdenes sólo valen para su partido, que el
selector ya no lo mueve, y que el «favorito» sale de la misma terna que la
barra.
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.queries.alineacion_enviada import AlineacionEnviada
from app.application.queries.league import LeagueQueryService
from app.domain.engines.prediccion import (
    CAMPOS,
    FACTOR_POR_TACTICA,
    goles_esperados,
    probabilidades_del_motor,
)
from tests.conftest import HT_TEAM_ID
from tests.test_league_matches_academy_queries import _with_league

#: En `_with_league` el próximo partido propio es Pulgas Arrechas (en casa)
#: contra Atlético Dos, con este `ht_match_id`.
RIVAL = 600_002
PROXIMO = 810_000
#: Y el último jugado por Pulgas Arrechas fue un 1-2 en casa del Deportivo Uno.
ULTIMO_PROPIO = 800_001

NORMAL, PRESIONAR, CONTRAATAQUES = 0, 1, 2

SECTORES = ("midfield", "right_def", "central_def", "left_def", "right_att", "central_att", "left_att")


def _lectura(valor: float, tactica: int, partido: int) -> dict[str, float]:
    return dict.fromkeys(CAMPOS, float(valor)) | {
        "tactic_type": float(tactica),
        "ht_match_id": float(partido),
    }


def _lecturas() -> dict[int, list[dict[str, float]]]:
    """Dos partidos por equipo, y el ÚLTIMO muy distinto del primero.

    Si el panel resumiera en vez de tomar el último, estos números no
    coincidirían con los de la cuenta hecha a mano sobre el último.
    """
    return {
        HT_TEAM_ID: [_lectura(20, NORMAL, 800_000), _lectura(40, CONTRAATAQUES, ULTIMO_PROPIO)],
        RIVAL: [_lectura(40, NORMAL, 700_001), _lectura(20, PRESIONAR, 700_002)],
        600_001: [_lectura(25, NORMAL, ULTIMO_PROPIO)],
        600_003: [_lectura(25, NORMAL, 800_000)],
    }


def _enviada(ht_match_id: int = PROXIMO) -> AlineacionEnviada:
    return AlineacionEnviada(ht_match_id, dict.fromkeys(SECTORES, 60), PRESIONAR)


def _proximo(
    enviada: AlineacionEnviada | None = None,
    metodo: str = "average",
    lecturas: dict[int, list[dict[str, float]]] | None = None,
) -> dict:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(
                team_id,
                runs=1000,
                lecturas=_lecturas() if lecturas is None else lecturas,
                metodo=metodo,
                enviada=enviada,
            )

    d = asyncio.run(go())
    assert d is not None and d.next_match is not None
    return d.next_match


def test_sin_ordenes_cada_lado_juega_con_su_ultimo_partido() -> None:
    nm = _proximo()
    assert nm["sources"]["own"]["kind"] == "last"
    assert nm["sources"]["rival"]["kind"] == "last"

    # Se nombra el partido del que sale tu lado.
    ultimo = nm["sources"]["own"]["match"]
    assert (ultimo["home"], ultimo["homeGoals"], ultimo["awayGoals"], ultimo["away"]) == (
        "Deportivo Uno",
        1,
        2,
        "Pulgas Arrechas",
    )

    # Los números son los del motor con el ÚLTIMO de cada uno --40 contra 20--
    # y la táctica de ese mismo partido, no la media ni la costumbre.
    mio, suyo = dict.fromkeys(CAMPOS, 40.0), dict.fromkeys(CAMPOS, 20.0)
    f_mio, f_suyo = FACTOR_POR_TACTICA[CONTRAATAQUES], FACTOR_POR_TACTICA[PRESIONAR]
    terna = probabilidades_del_motor(mio, suyo, f_mio, f_suyo)
    assert nm["homeWin"] == pytest.approx(terna.victoria, abs=1e-4)
    assert nm["expectedHomeGoals"] == pytest.approx(goles_esperados(mio, suyo, f_mio), abs=0.01)
    assert nm["sources"]["own"]["tactic"] == "Contraataques"
    assert nm["sources"]["rival"]["tactic"] == "Presionar"


def test_el_selector_de_proyeccion_ya_no_lo_mueve() -> None:
    """Un partido se juega con un once: el resumen de ocho equipos no pinta aquí."""
    assert _proximo(metodo="average") == _proximo(metodo="max")


def test_con_ordenes_tu_lado_usa_la_alineacion_enviada() -> None:
    nm = _proximo(_enviada())
    assert nm["sources"]["own"]["kind"] == "submitted"
    assert nm["sources"]["own"]["tactic"] == "Presionar"

    # Hattrick no prevé las indirectas a balón parado de unas órdenes: salen
    # de tu último partido, y la respuesta dice de cuál.
    assert nm["sources"]["own"]["setPiecesFrom"]["home"] == "Deportivo Uno"
    mio = dict.fromkeys(CAMPOS, 60.0) | {"sp_def": 40.0, "sp_att": 40.0}
    suyo = dict.fromkeys(CAMPOS, 20.0)
    # La táctica de las órdenes, NO la del último partido (Contraataques).
    f_mio = FACTOR_POR_TACTICA[PRESIONAR]
    assert nm["expectedHomeGoals"] == pytest.approx(goles_esperados(mio, suyo, f_mio), abs=0.01)


def test_unas_ordenes_de_otro_partido_no_se_cuelan() -> None:
    """Si llegan órdenes de otro cruce, tu lado cae a tu último partido."""
    assert _proximo(_enviada(ht_match_id=999_999)) == _proximo()


def test_el_favorito_sale_de_la_misma_terna_que_la_barra() -> None:
    """Antes salía de la Poisson de la temporada y la barra del modelo de zonas.

    Aquí las dos cosas discrepan a propósito: en la tabla Pulgas Arrechas es
    líder y Atlético Dos va tercero, así que la temporada lo da favorito; pero
    su último partido es flojísimo y el del rival brillante. La barra dice
    Atlético Dos, y el veredicto tiene que decir lo mismo.
    """
    lecturas = _lecturas()
    lecturas[HT_TEAM_ID][-1] = _lectura(10, NORMAL, ULTIMO_PROPIO)
    lecturas[RIVAL][-1] = _lectura(60, NORMAL, 700_002)
    nm = _proximo(lecturas=lecturas)
    assert nm["awayWin"] > nm["homeWin"]
    assert nm["verdict"] == "favorito Atlético Dos"


def test_sin_lecturas_no_hay_alineacion_que_nombrar() -> None:
    """Sin ratings se pronostica con los goles de la temporada, y se dice."""
    nm = _proximo(lecturas={})
    assert nm["sources"] is None
    assert nm["verdict"]
