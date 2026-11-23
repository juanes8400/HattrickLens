"""El selector de jornadas de «Mejor alineación» sólo ofrece las ya jugadas.

2026-11-23, pedido del usuario: aparecían jornadas que aún no habían
sucedido. Eran las de la temporada pasada de la misma serie, que llegan con
el mismo `series_ht_id`.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.application.queries.league import jornadas_ya_jugadas

INICIO_84 = datetime(2026, 11, 15, 22, 40, tzinfo=UTC)
INICIO_83 = INICIO_84 - timedelta(weeks=16)


def _partido(
    jornada: int, inicio: datetime, temporada: int | None, goles: int = 1
) -> SimpleNamespace:
    return SimpleNamespace(
        match_round=jornada,
        played_at=inicio + timedelta(weeks=jornada - 1),
        series_season=temporada,
        home_goals=goles,
        away_goals=0 if goles >= 0 else -1,
    )


def _jornada(
    jornada: int, inicio: datetime, temporada: int | None, goles: int = 1
) -> list[SimpleNamespace]:
    return [_partido(jornada, inicio, temporada, goles) for _ in range(4)]


def _temporada(inicio: datetime, temporada: int | None, jornadas: range) -> list[SimpleNamespace]:
    return [mt for j in jornadas for mt in _jornada(j, inicio, temporada)]


def test_no_ofrece_las_jornadas_de_la_temporada_pasada() -> None:
    partidos = _temporada(INICIO_83, 83, range(1, 15)) + _temporada(INICIO_84, 84, range(1, 3))
    jornadas = jornadas_ya_jugadas(partidos, rondas_jugadas=2, equipos=8)
    assert sorted(jornadas) == [1, 2]
    assert all(mt.series_season == 84 for mts in jornadas.values() for mt in mts)


def test_sin_etiqueta_de_temporada_tampoco_se_cuelan_ni_se_mezclan() -> None:
    # Lo sincronizado antes de que existiera la columna no lleva temporada.
    partidos = _temporada(INICIO_83, None, range(1, 15)) + _temporada(INICIO_84, None, range(1, 3))
    jornadas = jornadas_ya_jugadas(partidos, rondas_jugadas=2, equipos=8)
    assert sorted(jornadas) == [1, 2]
    # La jornada 1 son sus cuatro partidos de este año, no ocho de dos años.
    assert len(jornadas[1]) == 4
    assert all(mt.played_at >= INICIO_84 for mt in jornadas[1])


def test_lo_que_aun_no_se_ha_jugado_no_se_ofrece() -> None:
    partidos = _temporada(INICIO_84, 84, range(1, 3)) + _jornada(3, INICIO_84, 84, goles=-1)
    assert sorted(jornadas_ya_jugadas(partidos, rondas_jugadas=2, equipos=8)) == [1, 2]


def test_una_jornada_a_medias_no_cuenta() -> None:
    partidos = _temporada(INICIO_84, 84, range(1, 2)) + _jornada(2, INICIO_84, 84)[:3]
    assert sorted(jornadas_ya_jugadas(partidos, rondas_jugadas=2, equipos=8)) == [1]


def test_con_la_tabla_a_cero_no_hay_nada_que_elegir() -> None:
    partidos = _temporada(INICIO_83, 83, range(1, 15))
    assert jornadas_ya_jugadas(partidos, rondas_jugadas=0, equipos=8) == {}
