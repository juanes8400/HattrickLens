"""Clima del partido y qué especialidades favorece — 2026-08-18.

Hattrick decide el clima por REGIÓN, no por partido: el estadio donde se juega
está en una región y esa región tiene un clima hoy y otro mañana
(`regiondetails.xml`, campos `WeatherID` y `TomorrowWeatherID`). Como el
pronóstico solo llega a un día vista, este módulo solo sirve para el partido de
hoy o el de mañana; más allá, Hattrick tampoco lo sabe.

El clima únicamente mueve a tres especialidades, y solo con lluvia o con sol:
nublado y parcialmente nublado no tocan a nadie. Eso no es una simplificación
de esta app, es la regla del juego, y el tamaño del efecto también está
publicado: un 5% sobre TODAS las habilidades del jugador, arriba o abajo.

  · Técnico: +5% con sol, -5% con lluvia.
  · Potente: +5% con lluvia, -5% con sol.
  · Rápido:  -5% con lluvia y -5% con sol (nunca gana con el clima).
"""

from dataclasses import dataclass

RAIN = 0
OVERCAST = 1
PARTLY_CLOUDY = 2
SUNNY = 3

WEATHER_NAMES: dict[int, str] = {
    RAIN: "Lluvia",
    OVERCAST: "Nublado",
    PARTLY_CLOUDY: "Parcialmente nublado",
    SUNNY: "Soleado",
}

WEATHER_ICONS: dict[int, str] = {
    RAIN: "🌧️",
    OVERCAST: "☁️",
    PARTLY_CLOUDY: "⛅",
    SUNNY: "☀️",
}

# Cuánto mueve el clima, sobre TODAS las habilidades del jugador afectado.
EFFECT_PCT = 0.05

# Especialidad → efecto, por clima. +1 rinde un 5% por encima de lo normal, -1
# un 5% por debajo. Las que no aparecen no se ven afectadas por el clima en
# absoluto (Cabeceador, Imprevisible, Estoico, Influyente y los jugadores sin
# especialidad juegan igual llueva o haga sol).
EFFECTS: dict[int, dict[str, int]] = {
    RAIN: {"Potente": 1, "Técnico": -1, "Rápido": -1},
    SUNNY: {"Técnico": 1, "Potente": -1, "Rápido": -1},
    OVERCAST: {},
    PARTLY_CLOUDY: {},
}

# Las tres que reaccionan al clima, en el orden en que se enseñan.
WEATHER_SENSITIVE: tuple[str, ...] = ("Técnico", "Rápido", "Potente")


@dataclass(frozen=True)
class WeatherReading:
    """El clima de una región para un día concreto."""

    region_name: str
    weather_id: int

    @property
    def name(self) -> str:
        return WEATHER_NAMES.get(self.weather_id, "")

    @property
    def icon(self) -> str:
        return WEATHER_ICONS.get(self.weather_id, "")

    @property
    def known(self) -> bool:
        return self.weather_id in WEATHER_NAMES


def weather_name(weather_id: int) -> str:
    return WEATHER_NAMES.get(weather_id, "")


def favoured(weather_id: int) -> list[str]:
    """Especialidades que rinden por encima de lo normal con este clima."""
    return [s for s, e in EFFECTS.get(weather_id, {}).items() if e > 0]


def hindered(weather_id: int) -> list[str]:
    """Especialidades penalizadas con este clima."""
    return [s for s, e in EFFECTS.get(weather_id, {}).items() if e < 0]


def is_neutral(weather_id: int) -> bool:
    """¿Un clima que no mueve a nadie? Nublado y parcialmente nublado lo son.

    Merece decirse en voz alta: sin esto, un aviso de "hoy nublado" parecería
    incompleto, cuando en realidad la respuesta es que no hay nada que hacer.
    """
    return weather_id in WEATHER_NAMES and not EFFECTS.get(weather_id)
