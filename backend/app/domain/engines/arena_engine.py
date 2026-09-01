"""Arena Engine — ocupación, demanda insatisfecha y dimensionamiento del estadio.

PRECIOS. El precio de la entrada en Tribunas se derivó de forma exacta con los
datos de un solo partido: en el encuentro contra etbenianos1 tres sectores se
llenaron y solo Tribunas quedó a medias, así que la diferencia entre "ingresos
del partido" e "ingresos a estadio lleno" aísla ese sector:

    (630.527 - 535.090) / (10.808 - 5.785) = 19,0000 exacto

Los otros tres precios (General, Preferentes, Palcos) los confirmó el usuario
directamente — 2026-08-13, "para toda la herramienta" — así que los cuatro
sectores están verificados: `TICKET_PRICES_VERIFIED`.

DEMANDA INSATISFECHA. Cuando un sector se llena, la asistencia observada es un
límite inferior de la demanda real — está censurada. Ignorar eso lleva a
subestimar el retorno de una ampliación, que es el error clásico al decidir si
ampliar el estadio.
"""

from dataclasses import dataclass

SECTORS = ("general", "preferentes", "tribunas", "palcos")

# Precio por asiento en moneda local. Los cuatro sectores están verificados.
TICKET_PRICES: dict[str, float] = {
    "general": 7.0,
    "preferentes": 10.0,
    "tribunas": 19.0,  # verificado exactamente contra un partido real
    "palcos": 35.0,
}
TICKET_PRICES_VERIFIED = {"general", "preferentes", "tribunas", "palcos"}


@dataclass(frozen=True)
class ArenaCapacity:
    general: int
    preferentes: int
    tribunas: int
    palcos: int

    @property
    def total(self) -> int:
        return self.general + self.preferentes + self.tribunas + self.palcos

    def get(self, sector: str) -> int:
        return int(getattr(self, sector))


# Aquí vivían `Attendance`, `OccupancyReport` y `analyse_match`: la asistencia
# por sector, su ocupación, qué sectores se agotaron y el ingreso reconstruido
# multiplicando entradas por precio. Todo eso partía de `SoldTerraces`,
# `SoldBasic`, `SoldRoof` y `SoldVIP` de matchdetails, que son una función de
# HT Supporter, y las reglas de CHPP prohíben replicarlas (2026-09-01).
#
# Se borran en vez de dejarlas sin usar: código cuyo único propósito es
# calcular eso es exactamente lo que un revisor señalaría, esté llamado o no.
#
# `ArenaCapacity` se queda porque el aforo por sector es la configuración de
# tu propio estadio --llega por arenadetails-- y es lo que necesita el
# simulador de ampliación para saber cuánto cuesta cada asiento nuevo.


@dataclass
class ExpansionAnalysis:
    added_seats: dict[str, int]
    build_cost: float
    added_weekly_maintenance: float
    added_revenue_per_match: float
    home_matches_per_season: int
    payback_weeks: float | None
    net_per_season: float
    verdict: str


def analyse_expansion(
    added_seats: dict[str, int],
    build_cost_per_seat: dict[str, float],
    weekly_maintenance_per_seat: float,
    expected_fill_rate: float,
    home_matches_per_season: int = 7,
    season_weeks: int = 16,
    prices: dict[str, float] | None = None,
) -> ExpansionAnalysis:
    """¿Compensa ampliar? Compara la inversión con el retorno neto real.

    `expected_fill_rate` es la fracción de los asientos NUEVOS que se espera
    vender. Con sectores agotados la demanda está censurada, así que este
    parámetro debe venir de un modelo de demanda, no de la ocupación observada.
    """
    p = prices or TICKET_PRICES
    total_new = sum(added_seats.values())
    build_cost = sum(n * build_cost_per_seat.get(s, 0.0) for s, n in added_seats.items())
    added_maintenance = total_new * weekly_maintenance_per_seat
    added_revenue = sum(n * expected_fill_rate * p[s] for s, n in added_seats.items())

    revenue_per_season = added_revenue * home_matches_per_season
    cost_per_season = added_maintenance * season_weeks
    net_per_season = revenue_per_season - cost_per_season

    if net_per_season <= 0:
        payback = None
        verdict = "no compensaría: el mantenimiento superaría a los ingresos extra estimados"
    else:
        payback = build_cost / (net_per_season / season_weeks)
        verdict = (
            f"se amortizaría en ~{payback / season_weeks:.1f} temporadas (estimado)"
            if payback > 0
            else "amortización estimada inmediata"
        )

    return ExpansionAnalysis(
        added_seats=added_seats,
        build_cost=build_cost,
        added_weekly_maintenance=added_maintenance,
        added_revenue_per_match=added_revenue,
        home_matches_per_season=home_matches_per_season,
        payback_weeks=payback,
        net_per_season=net_per_season,
        verdict=verdict,
    )


# `estimate_true_demand` se retiró con lo anterior: estimaba la demanda REAL
# de un sector cuando se agotaba, que es la lectura más directa de la función
# de Supporter (2026-09-01).
