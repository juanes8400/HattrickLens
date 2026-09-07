"""Los ratings de la serie que alimentan el modelo de zonas.

Lo que se vigila aquí es el fallo que ya apareció dos veces: pedir un rating
con un nombre que el lector de partidos no usa. No revienta, no avisa, guarda
un cero — y un cero convertido en `A/(A+B)` deja de ser «no sé» para pasar a
ser «el rival gana ese duelo entero».
"""

import pytest

from app.application.queries.prediccion_liga import DEL_LECTOR, lecturas_de_la_serie
from app.domain.engines.prediccion import CAMPOS, proporcion


class _Partido:
    """Lo mínimo que la función lee de un partido de la serie."""

    def __init__(self, mid: int, local: int, visitante: int) -> None:
        self.ht_match_id = mid
        self.home_team_ht_id = local
        self.away_team_ht_id = visitante


class _Lector:
    """Un lector de partidos de mentira, con los nombres LARGOS de verdad."""

    def __init__(self) -> None:
        self.pedidos: list[int] = []

    async def fetch(self, _fichero: str, _version: str, **kw: int) -> dict:
        self.pedidos.append(kw["matchID"])
        def lado(equipo: int, base: int) -> dict:
            return {
                "team_id": equipo,
                "ratings": {
                    "midfield": base,
                    "left_def": base + 1,
                    "central_def": base + 2,
                    "right_def": base + 3,
                    "left_att": base + 4,
                    "central_att": base + 5,
                    "right_att": base + 6,
                    "set_pieces_def": base + 7,
                    "set_pieces_att": base + 8,
                },
            }
        return {"home": lado(10, 20), "away": lado(20, 30)}


class _Sesion:
    """Una sesión que no tiene ningún rating guardado."""

    async def execute(self, _q: object) -> object:
        class _R:
            @staticmethod
            def scalars() -> list:
                return []

        return _R()


def test_el_mapa_cubre_los_nueve_campos():
    """Si un campo del motor no está aquí, se lee `None` y se guarda cero."""
    assert set(DEL_LECTOR) == set(CAMPOS)


def test_balon_parado_se_pide_con_el_nombre_largo():
    """El fallo concreto que ya costó un 90,8 % donde la verdad era 44,5 %."""
    assert DEL_LECTOR["sp_def"] == "set_pieces_def"
    assert DEL_LECTOR["sp_att"] == "set_pieces_att"
    # Los otros siete sí coinciden, y por eso el fallo era tan silencioso:
    # siete de nueve variables funcionaban.
    assert all(DEL_LECTOR[c] == c for c in CAMPOS if not c.startswith("sp_"))


@pytest.mark.asyncio
async def test_las_lecturas_traen_balon_parado_de_verdad():
    lector = _Lector()
    lecturas = await lecturas_de_la_serie(
        _Sesion(), lector, "3.1", 9991, [_Partido(1, 10, 20), _Partido(2, 20, 10)]
    )
    assert set(lecturas) == {10, 20}
    for equipo in (10, 20):
        for lectura in lecturas[equipo]:
            assert set(lectura) == set(CAMPOS)
            # Ningún cero: el lector devolvió valores para los nueve.
            assert all(v > 0 for v in lectura.values())


@pytest.mark.asyncio
async def test_un_cero_en_balon_parado_no_es_un_valor_bajo():
    """Documenta por qué el mapa importa, con la aritmética delante.

    Con el nombre equivocado el rating se pierde, entra un cero, y la
    proporción pasa de decir «no sé» a afirmar que el rival gana el duelo
    entero. Esa es la diferencia entre 0,5 y 0,0.
    """
    assert proporcion(0, 34) == 0.0  # lo que salía con el fallo
    assert proporcion(0, 0) == 0.5  # lo que corresponde cuando no hay dato
    assert proporcion(18, 34) == pytest.approx(0.346, abs=0.001)  # el valor real


@pytest.mark.asyncio
async def test_no_se_repite_una_llamada_por_partido():
    """Un partido son dos equipos y UNA llamada: la respuesta trae los dos."""
    lector = _Lector()
    await lecturas_de_la_serie(
        _Sesion(), lector, "3.1", 9992, [_Partido(7, 10, 20), _Partido(8, 20, 10)]
    )
    assert lector.pedidos == [7, 8]


@pytest.mark.asyncio
async def test_sin_partidos_jugados_no_se_llama_a_nadie():
    lector = _Lector()
    assert await lecturas_de_la_serie(_Sesion(), lector, "3.1", 9993, []) == {}
    assert lector.pedidos == []
