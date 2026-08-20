"""El clima del partido: la regla del juego, el parser y el aviso.

Los números vienen de las reglas de Hattrick tal como las citó el usuario el
2026-08-18: un 5% sobre TODAS las habilidades, y solo para tres especialidades.
"""
from datetime import UTC, datetime

import pytest

from app.domain.engines import insights as ins
from app.domain.engines import weather as wx
from app.domain.value_objects.ht_time import ht_day, ht_to_utc
from app.infrastructure.chpp.parsers import get_parser

REGIONDETAILS = b"""<?xml version="1.0" encoding="utf-8"?>
<HattrickData>
  <FileName>regionDetails.xml</FileName>
  <Version>1.2</Version>
  <FetchedDate>2026-08-18 22:19:14</FetchedDate>
  <League>
    <LeagueID>19</LeagueID>
    <LeagueName>Colombia</LeagueName>
    <Region>
      <RegionID>576</RegionID>
      <RegionName>Bogot\xc3\xa1</RegionName>
      <WeatherID>3</WeatherID>
      <TomorrowWeatherID>2</TomorrowWeatherID>
      <NumberOfUsers>619</NumberOfUsers>
      <NumberOfOnline>18</NumberOfOnline>
    </Region>
  </League>
</HattrickData>"""

TEAMDETAILS = b"""<?xml version="1.0" encoding="utf-8"?>
<HattrickData>
  <Team>
    <TeamID>3271519</TeamID>
    <TeamName>Cauca CF</TeamName>
    <Arena><ArenaID>3268262</ArenaID><ArenaName>Cauca Stadium</ArenaName></Arena>
    <League><LeagueID>19</LeagueID><LeagueName>Colombia</LeagueName></League>
    <Country><CountryName>Colombia</CountryName></Country>
    <Region><RegionID>2379</RegionID><RegionName>Cauca</RegionName></Region>
  </Team>
</HattrickData>"""


# ── La regla ────────────────────────────────────────────────────────────────

def test_only_rain_and_sun_move_anyone() -> None:
    """Nublado y parcialmente nublado no tocan a nadie. No es que falte el
    dato: es que el juego no aplica nada."""
    assert wx.is_neutral(wx.OVERCAST)
    assert wx.is_neutral(wx.PARTLY_CLOUDY)
    assert not wx.is_neutral(wx.RAIN)
    assert not wx.is_neutral(wx.SUNNY)


def test_technical_and_powerful_are_mirror_images() -> None:
    assert wx.favoured(wx.SUNNY) == ["Técnico"]
    assert wx.favoured(wx.RAIN) == ["Potente"]
    assert "Técnico" in wx.hindered(wx.RAIN)
    assert "Potente" in wx.hindered(wx.SUNNY)


def test_quick_never_wins_with_the_weather() -> None:
    """Rápido es la única que pierde con los dos extremos y no gana con
    ninguno — por eso no puede escribirse como el simétrico de otra."""
    assert "Rápido" in wx.hindered(wx.RAIN)
    assert "Rápido" in wx.hindered(wx.SUNNY)
    assert not any("Rápido" in wx.favoured(w) for w in wx.WEATHER_NAMES)


def test_the_unaffected_specialties_appear_nowhere() -> None:
    for clima in wx.WEATHER_NAMES:
        movidas = set(wx.favoured(clima)) | set(wx.hindered(clima))
        assert movidas <= set(wx.WEATHER_SENSITIVE)


def test_the_effect_is_five_percent() -> None:
    assert wx.EFFECT_PCT == pytest.approx(0.05)


# ── El parser ───────────────────────────────────────────────────────────────

def test_regiondetails_keeps_today_and_tomorrow_apart() -> None:
    out = get_parser("regiondetails")(REGIONDETAILS)
    assert out["ht_region_id"] == 576
    assert out["region_name"] == "Bogotá"
    assert out["weather_today"] == wx.SUNNY
    assert out["weather_tomorrow"] == wx.PARTLY_CLOUDY
    # Sin la fecha del fichero, los dos números de arriba no se pueden situar
    # en el calendario.
    assert out["fetched_at"] == "2026-08-18 22:19:14"


def test_teamdetails_brings_the_region_of_any_team() -> None:
    """La región del rival sale de aquí y no de `arenadetails.xml`: ese
    fichero responde error 59 para un equipo que no gestionas —verificado en
    vivo el 2026-08-18—, y en un partido de visitante la región que manda es
    justo la del rival."""
    equipo = get_parser("teamdetails")(TEAMDETAILS)["teams"][0]
    assert equipo["ht_region_id"] == 2379
    assert equipo["region_name"] == "Cauca"


def test_hattrick_days_are_swedish_days() -> None:
    """Un partido de las 17:10 en Colombia son las 00:10 del día siguiente en
    el reloj de Hattrick, y "hoy"/"mañana" son días de ESE reloj."""
    assert ht_day(ht_to_utc("2026-08-19 00:10:00")) == datetime(
        2026, 8, 19, tzinfo=UTC
    ).date()


# ── El aviso ────────────────────────────────────────────────────────────────

def test_the_alert_names_both_sides_of_the_effect() -> None:
    aviso = ins.next_match_weather(
        123, "FC Rival", False, "Bogotá", wx.RAIN, tomorrow=True
    )[0]
    assert aviso.key == "match.weather.123"
    assert "mañana" in aviso.title
    assert "Potente" in aviso.detail
    assert "Técnico" in aviso.detail and "Rápido" in aviso.detail
    assert "5%" in aviso.detail
    assert aviso.evidence["favoured"] == ["Potente"]
    assert aviso.evidence["isHome"] is False


def test_a_neutral_sky_still_gets_an_alert_that_says_so() -> None:
    """Callar dejaría al manager sin saber si faltaba el dato o si no había
    efecto — que son cosas distintas."""
    aviso = ins.next_match_weather(
        7, "FC Rival", True, "Bogotá", wx.OVERCAST, tomorrow=False
    )[0]
    assert "no favorece ni penaliza" in aviso.detail
    assert aviso.evidence["favoured"] == []


def test_an_unknown_weather_id_says_nothing() -> None:
    """-1 es "CHPP no lo trajo". Inventar un cielo sería peor que callar."""
    assert ins.next_match_weather(7, "FC Rival", True, "Bogotá", -1, tomorrow=False) == []


def test_the_weather_key_expires_with_its_match() -> None:
    """Lleva el id del partido pegado por la misma razón que el déficit lleva
    la semana: el aviso de mañana es otro aviso. Y una vez jugado, su
    archivada no le sirve a nadie."""
    assert ins.is_known_key("match.weather.123")
    assert ins.week_scoped_root("match.weather.123") == "match.weather"


# ── La ventana de vigencia ──────────────────────────────────────────────────

async def _base(match_date: str, forecast_date: str):
    """Una base mínima: un equipo, un partido por jugarse y su pronóstico."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.db import models as m

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(m.Team(ht_team_id=537758, name="Pulgas Arrechas"))
        s.add(m.Match(
            ht_match_id=999, played_at=ht_to_utc(match_date), match_type=1,
            status="UPCOMING", home_team_ht_id=111, away_team_ht_id=537758,
            home_team_name="FC Rival", away_team_name="Pulgas Arrechas",
        ))
        s.add(m.MatchWeather(
            ht_match_id=999, venue_ht_team_id=111, ht_region_id=576,
            region_name="Bogotá", weather_today=wx.RAIN, weather_tomorrow=wx.SUNNY,
            forecast_taken_at=ht_to_utc(forecast_date),
            captured_at=ht_to_utc(forecast_date),
        ))
        await s.commit()
    return factory


async def _avisos(match_date: str, forecast_date: str) -> list[ins.Insight]:
    from sqlalchemy import select

    from app.api.v1.endpoints.analysis import _next_match_weather_insights
    from app.infrastructure.db import models as m

    factory = await _base(match_date, forecast_date)
    async with factory() as s:
        team = await s.scalar(select(m.Team))
        return await _next_match_weather_insights(s, team)


async def test_a_match_tomorrow_reads_the_tomorrow_forecast() -> None:
    avisos = await _avisos("2026-08-19 20:00:00", "2026-08-18 22:19:14")
    assert len(avisos) == 1
    assert avisos[0].evidence["weatherId"] == wx.SUNNY
    assert avisos[0].evidence["playedTomorrow"] is True
    # De visitante: la región que manda es la del rival, y así se dice.
    assert avisos[0].evidence["isHome"] is False
    assert "casa de FC Rival" in avisos[0].detail


async def test_a_match_today_reads_the_today_forecast() -> None:
    avisos = await _avisos("2026-08-18 20:00:00", "2026-08-18 08:00:00")
    assert avisos[0].evidence["weatherId"] == wx.RAIN
    assert avisos[0].evidence["playedTomorrow"] is False


async def test_a_stale_forecast_says_nothing() -> None:
    """El fichero solo trae hoy y mañana. Si el último sync es de anteayer,
    sus dos números ya no describen ningún día del futuro — enseñarlos sería
    dar por buena una predicción caducada."""
    assert await _avisos("2026-08-19 20:00:00", "2026-08-15 22:00:00") == []


async def test_a_match_further_out_says_nothing() -> None:
    """Hattrick tampoco lo sabe: no hay pronóstico a tres días."""
    assert await _avisos("2026-08-23 20:00:00", "2026-08-18 22:00:00") == []
