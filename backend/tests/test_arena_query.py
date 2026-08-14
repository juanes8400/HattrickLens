"""ArenaQueryService — con especial atención a la demanda censurada.

El caso que motiva la mitad de estos tests: si un sector se agota, la
asistencia observada mide asientos, no demanda. Un servicio que trate esa media
como demanda dirá siempre que la ampliación rinde justo lo que ya rinde el
estadio actual, y nunca podrá decir que te has quedado corto. Eso no es un
error de redondeo: es un sesgo que apunta siempre en la misma dirección.
"""
import asyncio
from datetime import UTC, datetime, timedelta

from app.application.queries.arena import ArenaQueryService
from app.infrastructure.db import models as m
from tests.conftest import seeded_session

BASE = datetime(2026, 3, 1, tzinfo=UTC)


async def _with_stadium(rows: list[dict]):
    factory, team_id = await seeded_session()
    async with factory() as s:
        for i, r in enumerate(rows):
            s.add(
                m.StadiumHistory(
                    team_id=team_id,
                    ht_match_id=900_000 + i,
                    played_at=BASE + timedelta(days=14 * i),
                    match_type=1,
                    capacity_total=r["capacity"],
                    capacity_terraces=r.get("cap_general"),
                    capacity_basic=r.get("cap_preferentes"),
                    capacity_roof=r.get("cap_tribunas"),
                    capacity_vip=r.get("cap_palcos"),
                    sold_terraces=r["general"],
                    sold_basic=r["preferentes"],
                    sold_roof=r["tribunas"],
                    sold_vip=r["palcos"],
                    revenue=r.get("revenue", 0),
                )
            )
        await s.commit()
    return factory, team_id


def _run(coro):
    return asyncio.run(coro)


# Capacidad real por sector: sin ella un lleno es indetectable (ver
# `test_without_a_sector_breakdown_censoring_cannot_be_evaluated`).
CAPS = {"cap_general": 12000, "cap_preferentes": 6000, "cap_tribunas": 1000, "cap_palcos": 1000}

HALF_EMPTY = [
    {"capacity": 20000, **CAPS,
     "general": 6000, "preferentes": 2500, "tribunas": 900, "palcos": 200},
    {"capacity": 20000, **CAPS,
     "general": 6400, "preferentes": 2600, "tribunas": 950, "palcos": 210},
    {"capacity": 20000, **CAPS,
     "general": 5800, "preferentes": 2400, "tribunas": 880, "palcos": 190},
]


def test_reports_occupancy_and_empty_seats() -> None:
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert d is not None
    assert d.capacity_is_real is True
    assert d.matches_analysed == 3
    assert len(d.matches) == 3
    assert all(mm.empty_seats > 0 for mm in d.matches)
    assert 0 < d.avg_occupancy < 100
    assert d.revenue_left_on_table > 0


def test_no_sell_out_means_demand_is_measurable() -> None:
    """Sin llenos, la ocupación observada sí mide demanda, y el servicio puede
    estimar el retorno de una ampliación sin advertencias."""
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert d.demand_is_censored is False
    assert d.censored_sectors == []
    assert any("Ningún sector se agotó" in n for n in d.notes)
    assert all(s.demand_is_censored is False for s in d.sectors)
    assert all(s.times_sold_out == 0 for s in d.sectors)


def test_a_sold_out_sector_is_flagged_as_censored() -> None:
    """Aquí está el punto: llenar tribunas todas las veces no significa que la
    demanda sean exactamente esos asientos. Significa que no sabemos cuántos
    más habrían entrado, y hay que decirlo."""
    full_roof = [{**r, "tribunas": 1000} for r in HALF_EMPTY]   # 1000/1000

    async def go():
        factory, team_id = await _with_stadium(full_roof)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert d.demand_is_censored is True
    assert "Tribunas" in d.censored_sectors
    roof = next(s for s in d.sectors if s.sector == "tribunas")
    assert roof.demand_is_censored is True
    assert roof.times_sold_out == 3
    note = " ".join(d.notes)
    assert "censurada" in note and "suelo" in note

    general = next(s for s in d.sectors if s.sector == "general")
    assert general.demand_is_censored is False


def test_expansion_options_are_ranked_and_costed() -> None:
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert len(d.expansion_options) == 3
    small, medium, large = d.expansion_options
    # Más asientos cuesta más construir y más mantener. Sin excepciones.
    assert small.build_cost < medium.build_cost < large.build_cost
    assert small.added_weekly_maintenance < large.added_weekly_maintenance
    for o in d.expansion_options:
        assert o.verdict
        if o.net_per_season <= 0:
            assert o.payback_seasons is None, "no se amortiza lo que pierde dinero"
        else:
            assert o.payback_seasons > 0


def test_fill_rate_can_be_overridden_and_is_declared() -> None:
    """Cuando la demanda está censurada, el usuario tiene que poder decir «yo
    creo que se llenaría al 90%» — y la respuesta debe admitir que ese número
    lo puso una persona, no los datos."""
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            svc = ArenaQueryService(s)
            return await svc.get(team_id), await svc.get(team_id, fill_rate=0.95)

    base, forced = _run(go())
    assert forced.expansion_options[0].added_revenue_per_match > (
        base.expansion_options[0].added_revenue_per_match
    )
    assert any("fijada a mano" in n for n in forced.notes)
    assert not any("fijada a mano" in n for n in base.notes)


def test_all_ticket_prices_are_verified() -> None:
    """Los cuatro precios los confirmó el usuario para toda la herramienta
    (2026-08-13) — ya no hay un sector "de la especificación, sin verificar",
    así que esa nota no debe aparecer."""
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert all(s.price_is_verified for s in d.sectors)
    assert not any("no está verificado" in n or "especificación" in n for n in d.notes)


def test_capacity_is_never_below_what_was_actually_sold() -> None:
    """Una ocupación superior al 100% es siempre un bug de derivación, no un
    lleno excepcional."""
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    for mm in d.matches:
        assert mm.occupancy <= 100.0
    for s in d.sectors:
        assert s.occupancy <= 100.0


def test_without_a_sector_breakdown_censoring_cannot_be_evaluated() -> None:
    """Este test existe por un fallo que casi se cuela.

    Si la capacidad por sector se deriva repartiendo el total en proporción a
    lo vendido, la ocupación sale idéntica en los cuatro sectores y un lleno
    deja de ser detectable — por construcción, no por falta de datos. El
    servicio tiene que negarse a evaluar la censura en ese caso en vez de
    devolver un `false` que parece una medida y es un artefacto.
    """
    no_breakdown = [
        {"capacity": 20000, "general": 6000, "preferentes": 2500,
         "tribunas": 900, "palcos": 200},
    ]

    async def go():
        factory, team_id = await _with_stadium(no_breakdown)
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert d.capacity_is_real is False
    assert d.demand_is_censored is False
    assert any("indetectable" in n for n in d.notes)
    assert any("orientativas" in n for n in d.notes)


def test_non_official_matches_are_always_excluded_from_stadium_stats() -> None:
    """Escaleras/Duelos (MatchType 50/62, HL-146) no deben sesgar la
    ocupación media, la calibración de precios ni el retorno de ampliar —
    y no hay override para incluirlos (2026-08-12, pedido explícito: "de
    TODOS los lugares de esta herramienta... ni con botón, ni sin botón")."""
    async def go():
        factory, team_id = await _with_stadium(HALF_EMPTY)
        async with factory() as s:
            s.add(m.StadiumHistory(
                team_id=team_id, ht_match_id=900_555, played_at=BASE + timedelta(days=100),
                match_type=50,
                capacity_total=20000, **{f"capacity_{k}": v for k, v in {
                    "terraces": CAPS["cap_general"], "basic": CAPS["cap_preferentes"],
                    "roof": CAPS["cap_tribunas"], "vip": CAPS["cap_palcos"],
                }.items()},
                sold_terraces=6000, sold_basic=2500, sold_roof=900, sold_vip=200,
            ))
            await s.commit()
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    d = _run(go())
    assert d.matches_analysed == 3


def test_a_team_without_stadium_history_returns_none() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await ArenaQueryService(s).get(team_id)

    assert _run(go()) is None
