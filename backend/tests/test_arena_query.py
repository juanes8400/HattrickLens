"""ArenaQueryService, ya sin el desglose por sector.

El 2026-09-01 esta pantalla dejo de trabajar con la asistencia POR SECTOR: es
una funcion de HT Supporter y las reglas de CHPP prohiben replicarla. Con ella
se fueron la mitad de los tests de este fichero -- los que probaban la demanda
censurada, los sectores agotados y el reparto de capacidad deducido de las
ventas --. Probaban bien lo que probaban; lo que probaban es lo que ya no se
puede hacer.

Lo que queda vigilado es lo que si es publico:

  * la asistencia TOTAL de cada partido y su ocupacion contra el aforo total,
  * la recaudacion que Hattrick reporta, sin estimarla cuando falta,
  * el simulador de ampliacion, que nunca necesito saber quien se sienta donde.
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
                    match_type=r.get("match_type", 1),
                    capacity_total=r["capacity"],
                    # El aforo por sector se conserva: es la configuracion de
                    # tu propio estadio y es lo que da el precio de un asiento
                    # nuevo en el simulador de ampliacion.
                    capacity_terraces=r.get("cap_general"),
                    capacity_basic=r.get("cap_preferentes"),
                    capacity_roof=r.get("cap_tribunas"),
                    capacity_vip=r.get("cap_palcos"),
                    sold_total=r["sold"],
                    revenue=r.get("revenue", 0),
                )
            )
        await s.commit()
    return factory, team_id


def _run(coro):
    return asyncio.run(coro)


CAPS = {"cap_general": 12000, "cap_preferentes": 6000, "cap_tribunas": 1000, "cap_palcos": 1000}

MEDIO_LLENO = [
    {"capacity": 20000, **CAPS, "sold": 9600, "revenue": 240_000},
    {"capacity": 20000, **CAPS, "sold": 10160, "revenue": 254_000},
    {"capacity": 20000, **CAPS, "sold": 9270, "revenue": 231_000},
]


def test_reports_occupancy_and_empty_seats() -> None:
    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert out.matches_analysed == 3
        assert out.capacity_total == 20000
        primero = out.matches[0]
        assert primero.sold == 9600
        assert primero.occupancy == 48.0
        assert primero.empty_seats == 10400
        # Sin fila en `matches` no hay nombre de rival: se cae a la fecha, que
        # es lo que rotulaba el eje antes y sigue identificando la barra.
        assert primero.rival == primero.date
        # La media de las tres ocupaciones observadas.
        assert 46 < out.avg_occupancy < 51

    _run(run())


def test_se_puede_mirar_solo_oficiales_o_solo_amistosos() -> None:
    """2026-09-13, pedido del usuario: un amistoso llena el estadio de otra
    manera. El aforo sale siempre de la última lectura, filtre lo que filtre."""
    from app.domain.value_objects.ht_constants import FRIENDLY_MATCH_TYPES

    amistoso = min(FRIENDLY_MATCH_TYPES)

    async def run() -> None:
        filas = [
            {"capacity": 20000, **CAPS, "sold": 18000, "match_type": 1},
            {"capacity": 20000, **CAPS, "sold": 4000, "match_type": amistoso},
        ]
        factory, team_id = await _with_stadium(filas)
        async with factory() as s:
            oficiales = await ArenaQueryService(s).get(team_id, tipo="oficiales")
            amistosos = await ArenaQueryService(s).get(team_id, tipo="amistosos")
            todos = await ArenaQueryService(s).get(team_id)
        assert oficiales is not None and amistosos is not None and todos is not None
        assert oficiales.matches_analysed == 1 and oficiales.avg_occupancy == 90.0
        assert amistosos.matches_analysed == 1 and amistosos.avg_occupancy == 20.0
        assert todos.matches_analysed == 2
        assert oficiales.capacity_total == amistosos.capacity_total == 20000

    _run(run())


def test_el_reparto_de_asientos_se_compara_con_el_recomendado() -> None:
    from app.application.queries.arena import REPARTO_RECOMENDADO, _hacia_el_reparto

    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert out.composition == {
            "general": 12000,
            "preferentes": 6000,
            "tribunas": 1000,
            "palcos": 1000,
        }
        assert abs(sum(out.recommended_shares.values()) - 1) < 1e-9

    _run(run())
    assert abs(sum(REPARTO_RECOMENDADO.values()) - 1) < 1e-9
    # Los cuatro sectores en la proporción recomendada, aunque a este estadio
    # le sobren palcos: 62,5 / 25 / 10 / 2,5 %.
    reparto = _hacia_el_reparto(
        {"general": 12000, "preferentes": 6000, "tribunas": 1000, "palcos": 1000}, 2500
    )
    # 1.562,5 y 62,5 empatan en resto: el asiento sobrante va a general.
    assert reparto == {"general": 1563, "preferentes": 625, "tribunas": 250, "palcos": 62}
    # Suma exacta: redondear sector a sector daba 2.501.
    assert sum(reparto.values()) == 2500


def test_si_cambia_el_aforo_el_conteo_empieza_de_nuevo() -> None:
    """2026-09-14, pedido del usuario: una ocupación medida contra el estadio
    de antes no dice nada del de ahora. Sólo cuentan los partidos jugados con
    el aforo actual, y la respuesta dice desde cuándo."""

    async def run() -> None:
        filas = [
            {"capacity": 18000, **CAPS, "sold": 17000},
            {"capacity": 18000, **CAPS, "sold": 17500},
            {"capacity": 20000, **CAPS, "sold": 10000},
            {"capacity": 20000, **CAPS, "sold": 12000},
        ]
        factory, team_id = await _with_stadium(filas)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert out.matches_analysed == 2
        assert [mm.sold for mm in out.matches] == [10000, 12000]
        assert out.avg_occupancy == 55.0
        assert out.capacity_changed_on == (BASE + timedelta(days=28)).date().isoformat()

    _run(run())


def test_sin_cambio_de_aforo_cuenta_todo() -> None:
    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert out.matches_analysed == 3
        assert out.capacity_changed_on is None

    _run(run())


def test_the_reported_revenue_is_used_and_never_invented() -> None:
    """Antes, si faltaba la recaudacion, se estimaba multiplicando las entradas
    de cada sector por su precio. Sin el desglose eso ya no se puede, y tampoco
    se inventa: un hueco se queda en hueco.

    OJO con lo que esto significa hoy: `revenue` NUNCA se rellena --el sync no
    lo escribe y la taquilla por partido no llega por ningun fichero--, asi que
    en la practica sale cero para todos. Por eso la pantalla dejo de enseñar un
    KPI de ingresos: un cero se lee como «no ingresaste nada» y es falso. El
    campo se conserva por si algun dia se recoge, y este test fija que si
    llega, se usa tal cual."""

    async def run() -> None:
        filas = [
            {"capacity": 20000, **CAPS, "sold": 9600, "revenue": 240_000},
            {"capacity": 20000, **CAPS, "sold": 9600},  # sin recaudacion
        ]
        factory, team_id = await _with_stadium(filas)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert out.matches[0].revenue > 0
        assert out.matches[1].revenue == 0
        assert out.total_revenue == out.matches[0].revenue

    _run(run())


def test_expansion_options_are_ranked_and_costed() -> None:
    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        # Tres tamaños, y desde el 2026-09-13 todos con los cuatro sectores en
        # la proporción recomendada, tenga el estadio lo que tenga.
        assert len(out.expansion_options) == 3
        for o in out.expansion_options:
            assert o.build_cost > 0
            assert o.verdict
            assert set(o.added_seats) == {"general", "preferentes", "tribunas", "palcos"}
        # La grande cuesta mas que la pequeña: el orden de la lista es el de
        # tamaño, no el de rentabilidad.
        assert out.expansion_options[-1].build_cost > out.expansion_options[0].build_cost
        tamanos = [sum(o.added_seats.values()) for o in out.expansion_options]
        assert tamanos == sorted(tamanos)

    _run(run())


def test_fill_rate_can_be_overridden_and_is_declared() -> None:
    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            fijado = await ArenaQueryService(s).get(team_id, fill_rate=0.95)
            observado = await ArenaQueryService(s).get(team_id)
        assert fijado is not None and observado is not None
        # Con mas llenado esperado, el ingreso por partido de la ampliacion sube.
        assert (
            fijado.expansion_options[0].added_revenue_per_match
            > observado.expansion_options[0].added_revenue_per_match
        )
        # Y se dice, para que nadie lea una estimacion a mano como si fuera
        # una observacion.
        assert any("fijada a mano" in n for n in fijado.notes)

    _run(run())


def test_occupancy_is_measured_against_todays_capacity_and_it_is_said() -> None:
    """No hay aforo historico por partido, asi que todas las ocupaciones usan
    el de hoy. Eso hace que un partido anterior a una ampliacion salga con
    menos ocupacion de la que tuvo, y hay que avisarlo."""

    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert all(mm.capacity == out.capacity_total for mm in out.matches)
        assert any("aforo de HOY" in n for n in out.notes)

    _run(run())


def test_non_official_matches_are_always_excluded_from_stadium_stats() -> None:
    """Torneos, duelos, escaleras y preparacion sesgan la ocupacion media y el
    retorno estimado de ampliar. Se excluyen siempre, con boton o sin el.

    OJO con la lista: los AMISTOSOS no estan en ella. `NON_OFFICIAL_MATCH_TYPES`
    son 50, 51, 60, 61 y 80 -- torneo, duelo, escalera y preparacion --, y un
    amistoso normal si cuenta para el estadio."""

    async def run() -> None:
        filas = [
            {"capacity": 20000, **CAPS, "sold": 9600, "revenue": 240_000},
            # Torneo (50): cuatro gatos, y no debe contar.
            {"capacity": 20000, **CAPS, "sold": 700, "revenue": 9_000, "match_type": 50},
        ]
        factory, team_id = await _with_stadium(filas)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert out.matches_analysed == 1
        assert out.matches[0].sold == 9600

    _run(run())


def test_cada_partido_dice_su_torneo_y_la_copa_por_su_nombre() -> None:
    """2026-09-14, pedido del usuario: el tooltip dice el torneo debajo del
    rival, y en copa no «Copa» sino cuál: «Copa Colombia», «Copa Cocuy Rubí»."""

    async def run() -> None:
        filas = [
            {"capacity": 20000, **CAPS, "sold": 9000, "match_type": 1},
            {"capacity": 20000, **CAPS, "sold": 9000, "match_type": 3},
            {"capacity": 20000, **CAPS, "sold": 9000, "match_type": 3},
            {"capacity": 20000, **CAPS, "sold": 9000, "match_type": 7},
        ]
        factory, team_id = await _with_stadium(filas)
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            # Una liga sin copas sembradas, para que sólo estén estas dos.
            team.ht_league_id = 777
            for i, (nivel, indice) in ((1, (1, 1)), (2, (2, 2))):
                s.add(
                    m.Match(
                        ht_match_id=900_000 + i,
                        played_at=BASE + timedelta(days=14 * i),
                        match_type=3,
                        status="FINISHED",
                        home_team_ht_id=team.ht_team_id,
                        away_team_ht_id=50 + i,
                        home_team_name="Local",
                        away_team_name=f"Rival {i}",
                        cup_level=nivel,
                        cup_level_index=indice,
                    )
                )
            s.add(
                m.WorldCup(
                    ht_league_id=777,
                    cup_league_level=0,
                    cup_level=1,
                    cup_level_index=1,
                    cup_name="Copa Colombia",
                )
            )
            s.add(
                m.WorldCup(
                    ht_league_id=777,
                    cup_league_level=0,
                    cup_level=2,
                    cup_level_index=2,
                    cup_name="Copa Cocuy Rubí",
                )
            )
            await s.commit()
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        assert [mm.tournament for mm in out.matches] == [
            "Liga",
            "Copa Colombia",
            "Copa Cocuy Rubí",
            "Hattrick Masters",
        ]

    _run(run())


def test_a_team_without_stadium_history_returns_none() -> None:
    async def run() -> None:
        factory, team_id = await seeded_session()
        async with factory() as s:
            assert await ArenaQueryService(s).get(team_id) is None

    _run(run())


def test_the_response_carries_nothing_per_sector() -> None:
    """La red de seguridad de esta pantalla: si alguien reintroduce el desglose
    por la puerta de atras, el contrato lo delata."""

    async def run() -> None:
        factory, team_id = await _with_stadium(MEDIO_LLENO)
        async with factory() as s:
            out = await ArenaQueryService(s).get(team_id)
        assert out is not None
        campos = set(vars(out))
        for prohibido in ("sectors", "sold_out_matches", "demand_is_censored", "censored_sectors"):
            assert prohibido not in campos, f"«{prohibido}» es desglose por sector"
        assert not any("sold_out" in c for c in vars(out.matches[0]))

    _run(run())
