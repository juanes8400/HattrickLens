"""La asignación óptima, contra fuerza bruta.

2026-08-26. Un algoritmo de emparejamiento no falla con un error: falla
devolviendo una respuesta peor en silencio, y nadie se entera. Por eso aquí se
compara contra la mejor de TODAS las permutaciones en cientos de matrices al
azar, en vez de fijar unos cuantos casos a mano.
"""

import itertools
import random  # noqa: S311 — es una prueba, no criptografia

from app.domain.engines.asignacion_optima import asignacion_maxima


def _mejor_por_fuerza_bruta(m: list[list[float]], filas: int, columnas: int) -> float:
    """La suma máxima probando todas las formas de repartir las columnas."""
    mejor = float("-inf")
    for combo in itertools.permutations(range(filas), columnas):
        mejor = max(mejor, sum(m[combo[j]][j] for j in range(columnas)))
    return mejor


def _suma(m: list[list[float]], pares: list[tuple[int, int]]) -> float:
    return sum(m[i][j] for i, j in pares)


def test_el_caso_que_rompe_al_avaricioso():
    """Coger la mejor pareja primero da 10; el óptimo da 17."""
    m = [[10.0, 9.0], [8.0, 0.0]]
    pares = asignacion_maxima([0, 1], [0, 1], lambda i, j, m=m: m[i][j])
    assert _suma(m, pares) == 17.0


def test_coincide_con_la_fuerza_bruta_en_cuadradas():
    rnd = random.Random(20260826)  # noqa: S311
    for _ in range(150):
        n = rnd.randint(1, 6)
        m = [[rnd.randint(0, 20) * 1.0 for _ in range(n)] for _ in range(n)]
        pares = asignacion_maxima(list(range(n)), list(range(n)), lambda i, j, m=m: m[i][j])
        assert len(pares) == n
        assert _suma(m, pares) == _mejor_por_fuerza_bruta(m, n, n)


def test_coincide_con_la_fuerza_bruta_con_mas_candidatos_que_plazas():
    """El caso real: dieciocho canteranos para once sillas."""
    rnd = random.Random(1)  # noqa: S311
    for _ in range(150):
        filas = rnd.randint(2, 7)
        columnas = rnd.randint(1, filas)
        m = [[rnd.randint(0, 30) * 1.0 for _ in range(columnas)] for _ in range(filas)]
        pares = asignacion_maxima(
            list(range(filas)), list(range(columnas)), lambda i, j, m=m: m[i][j]
        )
        assert len(pares) == columnas
        assert _suma(m, pares) == _mejor_por_fuerza_bruta(m, filas, columnas)


def test_cada_plaza_y_cada_candidato_una_sola_vez():
    rnd = random.Random(7)  # noqa: S311
    m = [[rnd.random() for _ in range(5)] for _ in range(9)]
    pares = asignacion_maxima(list(range(9)), list(range(5)), lambda i, j, m=m: m[i][j])
    assert len({i for i, _ in pares}) == 5
    assert {j for _, j in pares} == set(range(5))


def test_faltan_candidatos_para_tantas_plazas():
    """Tres sillas y dos chicos: se llenan dos y la otra se queda vacía."""
    m = [[5.0, 1.0, 2.0], [3.0, 9.0, 4.0]]
    pares = asignacion_maxima([0, 1], [0, 1, 2], lambda i, j, m=m: m[i][j])
    assert len(pares) == 2
    assert _suma(m, pares) == 14.0  # 5 + 9


def test_todo_a_cero_sigue_llenando():
    """Sin nada que descubrir, las plazas se ocupan igual: el once se juega."""
    pares = asignacion_maxima([0, 1, 2], [0, 1], lambda i, j: 0.0)
    assert len(pares) == 2


def test_es_estable_entre_llamadas():
    """Dos recargas con los mismos datos tienen que dar el mismo once."""
    rnd = random.Random(99)  # noqa: S311
    m = [[rnd.randint(0, 4) * 1.0 for _ in range(4)] for _ in range(8)]
    a = asignacion_maxima(list(range(8)), list(range(4)), lambda i, j, m=m: m[i][j])
    b = asignacion_maxima(list(range(8)), list(range(4)), lambda i, j, m=m: m[i][j])
    assert a == b


def test_sin_nada_que_repartir():
    assert asignacion_maxima([], [1, 2], lambda i, j: 1.0) == []
    assert asignacion_maxima([1, 2], [], lambda i, j: 1.0) == []


def test_una_matriz_del_tamano_real_no_tarda():
    """Dieciocho canteranos, once plazas: tiene que ser instantáneo."""
    rnd = random.Random(3)  # noqa: S311
    m = [[rnd.random() * 100 for _ in range(11)] for _ in range(18)]
    pares = asignacion_maxima(list(range(18)), list(range(11)), lambda i, j, m=m: m[i][j])
    assert len(pares) == 11
    # Y mejor que cualquier reparto por turnos ingenuo.
    avaricioso = 0.0
    usados: set[int] = set()
    for j in range(11):
        i = max((x for x in range(18) if x not in usados), key=lambda x: m[x][j])
        usados.add(i)
        avaricioso += m[i][j]
    assert _suma(m, pares) >= avaricioso
