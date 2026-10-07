"""La venta que todavía no existe tiene que costar lo mismo que la que existirá.

«Plantilla actual», en Transferencias, pregunta qué dejaría vender HOY a
alguien que sigue en el club. La cifra sale de multiplicar el precio por lo
que se lleva la casa, y ese porcentaje NO puede ser una copia aparte: el día
que la venta ocurra de verdad, el libro de transferencias tiene que decir
exactamente lo mismo que dijo la simulación.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.engines.player_balance import (
    ACADEMY_FIRST_SALE_PCT,
    PlayerTransferRecord,
    SalarySnapshot,
    agent_pct_de_una_venta,
    compute_balance,
)

COMPRADO = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _registro(
    *,
    sale_price: int | None,
    sold_at: datetime | None,
    is_academy_graduate: bool = False,
    as_of: datetime,
) -> PlayerTransferRecord:
    return PlayerTransferRecord(
        purchase_price=None if is_academy_graduate else 1_000_000,
        purchased_at=COMPRADO,
        is_academy_graduate=is_academy_graduate,
        salary_history=[SalarySnapshot(captured_at=COMPRADO, salary=12_000)],
        listing_count=1,
        sale_price=sale_price,
        sold_at=sold_at,
        economy_date=COMPRADO + timedelta(days=1),
        promotion_cost=20_000 if is_academy_graduate else 0,
        as_of=as_of,
    )


@pytest.mark.parametrize("dias", [4, 10, 25, 60, 200])
def test_lo_simulado_hoy_es_lo_que_cobrara_la_venta_de_hoy(dias: int) -> None:
    """El porcentaje de la simulación y el de la venta real son el mismo."""
    hoy = COMPRADO + timedelta(days=dias)
    simulado = agent_pct_de_una_venta(COMPRADO, hoy, is_academy_graduate=False)
    vendido = compute_balance(_registro(sale_price=4_000_000, sold_at=hoy, as_of=hoy))
    assert vendido.agent_pct == pytest.approx(simulado)


@pytest.mark.parametrize("precio", [0, 150_000, 4_000_000, 90_000_000])
def test_el_saldo_simulado_cuadra_con_lo_invertido(precio: int) -> None:
    """Neto menos gastos: lo que la pantalla escribe como fórmula.

    Los gastos se leen de la MISMA etapa sin vender, para que la simulación no
    tenga su propia idea de lo que costó el jugador.
    """
    hoy = COMPRADO + timedelta(days=30)
    sin_vender = compute_balance(_registro(sale_price=None, sold_at=None, as_of=hoy))
    gastos = (
        (sin_vender.purchase_price or 0) + sin_vender.salary_total + sin_vender.listing_cost
    )

    pct = agent_pct_de_una_venta(COMPRADO, hoy, is_academy_graduate=False)
    neto = round(precio * (1 - pct))
    saldo_simulado = neto - gastos + sin_vender.resale_bonus_share

    vendido = compute_balance(_registro(sale_price=precio, sold_at=hoy, as_of=hoy))
    assert vendido.net_sale_proceeds == neto
    assert vendido.saldo == pytest.approx(saldo_simulado)
    # Y lo que costó no cambia por venderlo: los mismos gastos antes y después.
    assert (
        vendido.purchase_price or 0
    ) + vendido.salary_total + vendido.listing_cost == gastos


def test_un_canterano_paga_el_plano_tambien_en_la_simulacion() -> None:
    """Su primera venta son 5 % y ya, sin tabla de días."""
    hoy = COMPRADO + timedelta(days=45)
    assert (
        agent_pct_de_una_venta(COMPRADO, hoy, is_academy_graduate=True)
        == ACADEMY_FIRST_SALE_PCT
    )
    vendido = compute_balance(
        _registro(sale_price=2_000_000, sold_at=hoy, is_academy_graduate=True, as_of=hoy)
    )
    assert vendido.agent_pct == pytest.approx(ACADEMY_FIRST_SALE_PCT)


def test_la_fila_de_quien_sigue_en_el_club_trae_el_porcentaje_de_hoy() -> None:
    """Sin vender no hay `agent_pct`, y por eso hace falta el de la simulación.

    Es la razón de que la fila lleve los dos campos: el de la venta real es
    `None` mientras no haya venta, y la pantalla necesita algo que multiplicar.
    """
    hoy = COMPRADO + timedelta(days=30)
    sin_vender = compute_balance(_registro(sale_price=None, sold_at=None, as_of=hoy))
    assert sin_vender.is_sold is False
    assert sin_vender.agent_pct == 0.0
    assert agent_pct_de_una_venta(COMPRADO, hoy, is_academy_graduate=False) > 0
