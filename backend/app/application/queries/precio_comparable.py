"""Lo que ha costado la gente parecida a un jugador tuyo, para la pantalla.

No llama a Hattrick ni una vez: todo sale del fondo que dejó el paso semanal,
así que abrir la ficha de un jugador es gratis y se puede recalcular tantas
veces como haga falta. Por eso tampoco hay nada que invalidar cuando el jugador
sube una habilidad o cumple años: sus comparables se vuelven a medir contra el
jugador de hoy y los que dejan de parecerse se caen solos.

Lo que la pantalla está obligada a decir, y por eso viaja aquí:

· **Cuántos son provisionales.** Una venta entra con la puja de precio hasta
  que su subasta cierra. La puja se queda corta: el 2026-10-05 Valerio Cataldi
  tenía 65.000.000 de puja y cerró en 77.720.000, un 16% más.
· **De cuándo es lo más viejo.** Una venta sigue contando pasadas las siete
  semanas si no apareció nada mejor, y entonces el número habla de un mercado
  que puede haber cambiado.
· **Cuánto se parecen de verdad.** El peso de cada uno, para que se vea si el
  número sale de gemelos o de primos lejanos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.mercado_comparable import a_guardado
from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    VIDA,
    Guardado,
    Objetivo,
    comparables_de,
    estimar,
    objetivo_de,
)
from app.infrastructure.db import models as m

#: Las ocho habilidades del jugador propio. `terna` descarta resistencia y
#: balón parado; pedirlas todas evita que este módulo tenga que saber cuáles.
HABILIDADES = (
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
    "stamina",
)


@dataclass(frozen=True, slots=True)
class RasgoVisible:
    """Una habilidad y su nivel, SIN formatear.

    El nombre sale con la clave interna a proposito: quien lo pinte tiene el
    glosario oficial de Hattrick y sabe como se llama «scoring» en el idioma
    de quien mira. Montar aqui la cadena obligaria a traducir en el servidor,
    que no sabe el idioma, y fue justo el fallo que se vio en pantalla el
    2026-10-06: el perfil salia como «scoring 18 - passing 13».
    """

    habilidad: str
    nivel: int


@dataclass(frozen=True, slots=True)
class FilaDeComparable:
    """Una venta, tal como se enseña."""

    ht_player_id: int
    nombre: str
    precio: int
    peso: int
    firme: bool
    viejo: bool
    edad: int
    perfil: tuple[RasgoVisible, RasgoVisible, RasgoVisible]
    semanas: int


@dataclass(frozen=True, slots=True)
class PrecioComparable:
    """El número y todo lo que hace falta para no leerlo mal."""

    #: `None` mientras no haya bastantes ventas.
    media: int | None
    mediana: int | None
    #: Los dos extremos de lo que de verdad se pagó.
    minimo: int | None
    maximo: int | None
    n: int
    faltan: int
    peso_minimo: int
    provisionales: int
    #: Semanas de la venta más vieja de las que cuentan.
    semanas_del_mas_viejo: int
    #: El perfil con el que se buscó, para que se vea contra qué se compara.
    perfil: tuple[RasgoVisible, RasgoVisible, RasgoVisible]
    comparables: tuple[FilaDeComparable, ...]


async def precio_de(
    session: AsyncSession,
    team_id: int,
    ht_player_id: int,
    ahora: datetime | None = None,
) -> PrecioComparable | None:
    """El precio de un jugador, o `None` si ese jugador no es de este equipo."""
    momento = ahora or datetime.now(UTC)
    objetivo = await _objetivo_del_jugador(session, team_id, ht_player_id)
    if objetivo is None:
        return None

    filas = (
        await session.execute(select(m.MarketSale).where(m.MarketSale.team_id == team_id))
    ).scalars()
    elegidos = comparables_de([a_guardado(f) for f in filas], objetivo, momento)
    estimacion = estimar(elegidos)
    precios = [c.venta.precio for c in elegidos]

    return PrecioComparable(
        media=estimacion.media,
        mediana=estimacion.mediana,
        minimo=min(precios) if estimacion.suficiente else None,
        maximo=max(precios) if estimacion.suficiente else None,
        n=estimacion.n,
        faltan=max(0, OBJETIVO - estimacion.n),
        peso_minimo=estimacion.peso_minimo,
        provisionales=estimacion.provisionales,
        semanas_del_mas_viejo=max(
            (_semanas(c.venta.visto_el, momento) for c in elegidos), default=0
        ),
        perfil=_perfil(objetivo),
        comparables=tuple(
            FilaDeComparable(
                ht_player_id=c.venta.ht_player_id,
                nombre=c.venta.nombre,
                precio=c.venta.precio,
                peso=c.peso,
                firme=c.venta.firme,
                viejo=c.viejo,
                edad=c.venta.edad,
                perfil=_perfil(c.venta),
                semanas=_semanas(c.venta.visto_el, momento),
            )
            for c in elegidos
        ),
    )


async def _objetivo_del_jugador(
    session: AsyncSession, team_id: int, ht_player_id: int
) -> Objetivo | None:
    jugador = (
        await session.execute(
            select(m.Player).where(
                m.Player.team_id == team_id, m.Player.ht_player_id == ht_player_id
            )
        )
    ).scalar_one_or_none()
    if jugador is None:
        return None
    foto = (
        await session.execute(
            select(m.PlayerSnapshot)
            .where(m.PlayerSnapshot.player_id == jugador.id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if foto is None:
        return None
    return objetivo_de(
        ht_player_id,
        foto.age_years or 0,
        {h: getattr(foto, h, 0) or 0 for h in HABILIDADES},
        especialidad=foto.specialty or 0,
    )


def _perfil(quien: Objetivo | Guardado) -> tuple[RasgoVisible, RasgoVisible, RasgoVisible]:
    """Las tres habilidades que deciden el parecido, sin formatear."""
    return (
        RasgoVisible(quien.primaria.habilidad, quien.primaria.nivel),
        RasgoVisible(quien.secundaria.habilidad, quien.secundaria.nivel),
        RasgoVisible(quien.terciaria.habilidad, quien.terciaria.nivel),
    )


def _semanas(desde: datetime, ahora: datetime) -> int:
    inicio = desde if desde.tzinfo is not None else desde.replace(tzinfo=UTC)
    fin = ahora if ahora.tzinfo is not None else ahora.replace(tzinfo=UTC)
    return max(0, int((fin - inicio) / VIDA * 7))
