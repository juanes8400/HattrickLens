"""Tests del motor de estadio.

El 2026-09-01 se retiraron los que probaban la asistencia POR SECTOR
--`analyse_match`, `estimate_true_demand`, y con ellos el reparto de ocupacion
y la demanda censurada--. Eran cinco y probaban bien lo que probaban; el
problema es que lo que probaban es una funcion de HT Supporter, y las reglas de
CHPP prohiben replicarla.

Sobrevive el simulador de ampliacion, que nunca necesito saber quien se sienta
donde: solo los asientos que añadirias, su coste y el llenado medio esperado.
"""

from app.domain.engines.arena_engine import (
    TICKET_PRICES,
    ArenaCapacity,
    analyse_expansion,
)

CAP = ArenaCapacity(general=34_130, preferentes=13_639, tribunas=10_808, palcos=1_425)


def test_capacity_matches_screen() -> None:
    assert CAP.total == 60_002


def test_roof_ticket_price_is_exactly_nineteen() -> None:
    """Calibrado en su dia contra los ingresos reales de un partido.

    El precio se conserva --lo necesita el simulador para valorar un asiento
    nuevo-- aunque la comprobacion original ya no se pueda rehacer: comparaba
    el ingreso real con el de estadio lleno POR SECTOR.
    """
    assert TICKET_PRICES["tribunas"] == 19.0


def test_expansion_pays_off_when_demand_exists() -> None:
    r = analyse_expansion(
        added_seats={"general": 10_000},
        build_cost_per_seat={"general": 450.0},
        weekly_maintenance_per_seat=0.7,
        expected_fill_rate=0.95,       # sector agotado: se llenaría casi entero
        home_matches_per_season=7,
    )
    assert r.net_per_season > 0
    assert r.payback_weeks is not None
    assert "amortiza" in r.verdict


def test_expansion_rejected_when_seats_stay_empty() -> None:
    r = analyse_expansion(
        added_seats={"tribunas": 10_000},
        build_cost_per_seat={"tribunas": 1_000.0},
        weekly_maintenance_per_seat=3.0,
        expected_fill_rate=0.05,       # ya sobran asientos en ese sector
        home_matches_per_season=7,
    )
    assert r.net_per_season < 0
    assert r.payback_weeks is None
    assert "no compensa" in r.verdict
