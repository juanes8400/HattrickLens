"""HTMS y HTMS28 — el valor de un jugador y su potencial a los 28.

HTMS no es la suma de los niveles: cada habilidad aporta puntos según una
tabla, y la tabla crece mucho más deprisa que el nivel (de 16 a 17 en Defensa
son 150 puntos; de 3 a 4, veintiséis). Por eso dos jugadores con la misma
"suma de estrellas" pueden valer cosas muy distintas.

HTMS28 no mide nada del jugador: proyecta cuántos puntos acumularía si lo
entrenaras sin parar hasta los 28 años, con entrenador bueno, ayudantes
alrededor de 8.23 y 10% de forma física. Es una comparación entre edades, no
una promesa — un chico de 17 sale altísimo porque le quedan once temporadas de
entrenamiento por delante, no porque sea mejor.

Fórmulas y tablas: docs/reference/htms_formulas_hattrick.html
"""

from dataclasses import dataclass

# Puntos por nivel y habilidad, en el orden en que Hattrick las nombra:
# portería, defensa, jugadas, lateral, pases, anotación, balón parado.
# El techo por habilidad (nivel 20-23 según cuál) es de la implementación
# original; se conserva tal cual para dar el mismo número que Foxtrick.
TABLA: dict[int, tuple[int, int, int, int, int, int, int]] = {
    0: (0, 0, 0, 0, 0, 0, 0),
    1: (2, 4, 4, 2, 3, 4, 1),
    2: (12, 18, 17, 12, 14, 17, 2),
    3: (23, 39, 34, 25, 31, 36, 5),
    4: (39, 65, 57, 41, 51, 59, 9),
    5: (56, 98, 84, 60, 75, 88, 15),
    6: (76, 134, 114, 81, 104, 119, 21),
    7: (99, 175, 150, 105, 137, 156, 28),
    8: (123, 221, 190, 132, 173, 197, 37),
    9: (150, 271, 231, 161, 213, 240, 46),
    10: (183, 330, 281, 195, 259, 291, 56),
    11: (222, 401, 341, 238, 315, 354, 68),
    12: (268, 484, 412, 287, 381, 427, 81),
    13: (321, 580, 493, 344, 457, 511, 95),
    14: (380, 689, 584, 407, 540, 607, 112),
    15: (446, 809, 685, 478, 634, 713, 131),
    16: (519, 942, 798, 555, 738, 830, 153),
    17: (600, 1092, 924, 642, 854, 961, 179),
    18: (691, 1268, 1070, 741, 988, 1114, 210),
    19: (797, 1487, 1247, 855, 1148, 1300, 246),
    20: (924, 1791, 1480, 995, 1355, 1547, 287),
    21: (1074, 1791, 1791, 1172, 1355, 1547, 334),
    22: (1278, 1791, 1791, 1360, 1355, 1547, 388),
    23: (1278, 1791, 1791, 1360, 1355, 1547, 450),
}

NIVEL_MAXIMO = max(TABLA)

# Puntos HTMS que genera una semana de entrenamiento a cada edad. Bajan con la
# edad porque el entrenamiento rinde menos.
#
# El 6.45 a los 42 años rompe la bajada (venía de 5.65 a los 41). Está así en
# la implementación de la que salen estas tablas; se conserva a propósito, para
# dar el mismo número que da Foxtrick, en vez de "arreglarlo" y desviarse.
PUNTOS_POR_SEMANA: dict[int, float] = {
    17: 10.00,
    18: 9.92,
    19: 9.81,
    20: 9.69,
    21: 9.54,
    22: 9.39,
    23: 9.22,
    24: 9.04,
    25: 8.85,
    26: 8.66,
    27: 8.47,
    28: 8.27,
    29: 8.07,
    30: 7.87,
    31: 7.67,
    32: 7.47,
    33: 7.27,
    34: 7.07,
    35: 6.87,
    36: 6.67,
    37: 6.47,
    38: 6.26,
    39: 6.06,
    40: 5.86,
    41: 5.65,
    42: 6.45,
    43: 6.24,
    44: 6.04,
    45: 5.83,
}

EDAD_OBJETIVO = 28
DIAS_POR_ANO = 112
DIAS_POR_SEMANA = 7

_MIN_EDAD = min(PUNTOS_POR_SEMANA)
_MAX_EDAD = max(PUNTOS_POR_SEMANA)


@dataclass(frozen=True)
class Htms:
    ability: int
    potential: int

    @property
    def margen(self) -> int:
        """Lo que le queda por crecer (o lo que ya dejó atrás, si es negativo)."""
        return self.potential - self.ability


def _puntos(nivel: int | None, columna: int) -> int:
    if nivel is None or nivel <= 0:
        return 0
    return TABLA[min(int(nivel), NIVEL_MAXIMO)][columna]


def ability(
    keeper: int | None,
    defending: int | None,
    playmaking: int | None,
    winger: int | None,
    passing: int | None,
    scoring: int | None,
    set_pieces: int | None,
) -> int:
    """Suma de los siete aportes. Una habilidad desconocida cuenta 0."""
    valores = (keeper, defending, playmaking, winger, passing, scoring, set_pieces)
    return sum(_puntos(nivel, i) for i, nivel in enumerate(valores))


def _semana(edad: int) -> float:
    return PUNTOS_POR_SEMANA[min(max(edad, _MIN_EDAD), _MAX_EDAD)]


def potential(ability_actual: int, age_years: int, age_days: int) -> int:
    """HTMS28: lo que tendría a los 28 entrenando sin parar desde hoy.

    Antes de los 28 se suma lo que falta; después se resta lo ya entrenado de
    más, que es la misma cuenta al revés. Para un veterano el número deja de
    querer decir "potencial" y pasa a ser "cuánto valía a los 28", así que se
    interpreta con pinzas.
    """
    dias = max(0, min(int(age_days), DIAS_POR_ANO - 1))
    edad = int(age_years)

    if edad < EDAD_OBJETIVO:
        # Lo que queda del año en curso, más las temporadas enteras que faltan.
        resto_del_ano = (DIAS_POR_ANO - dias) / DIAS_POR_SEMANA * _semana(edad)
        anos_enteros = sum(16 * _semana(k) for k in range(edad + 1, EDAD_OBJETIVO))
        return round(ability_actual + resto_del_ano + anos_enteros)

    # 28 o más: se descuenta lo entrenado desde que los cumplió.
    transcurrido = dias / DIAS_POR_SEMANA * _semana(edad)
    transcurrido += sum(16 * _semana(k) for k in range(EDAD_OBJETIVO, edad))
    return round(ability_actual - transcurrido)


def de_habilidades(
    age_years: int,
    age_days: int,
    keeper: int | None = None,
    defending: int | None = None,
    playmaking: int | None = None,
    winger: int | None = None,
    passing: int | None = None,
    scoring: int | None = None,
    set_pieces: int | None = None,
) -> Htms:
    a = ability(keeper, defending, playmaking, winger, passing, scoring, set_pieces)
    return Htms(ability=a, potential=potential(a, age_years, age_days))
