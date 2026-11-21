"""Alertas generales de la plantilla (2026-11-18, definidas por el usuario).

Los umbrales son los suyos, dichos uno a uno:

* Resistencia baja: 2 niveles o más por debajo de lo esperado para su edad
  (tabla de resistencia de Federación Ocerin, la misma que dibuja la ficha).
* Precio que sube: +15 % en una semana.
* Titular sin experiencia: 3 niveles o más por debajo de la media del once.
* Juvenil listo: 17 años y 0 días o más, y al menos 112 días en la academia.
* Titular que no juega: ninguno de los 2 últimos partidos oficiales.

Funciones puras: reciben lo ya leído y devuelven `Insight`.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.engines.cruces_de_equilibrio import Cruce
from app.domain.engines.insights import Insight, Severity
from app.domain.value_objects.formatting import thousands

NIVELES_DE_RESISTENCIA_BAJA = 2
#: En puntos porcentuales y con enteros: 115/100 - 1 en coma flotante da 0,1499…
SUBIDA_DE_PRECIO_PCT = 15
NIVELES_DE_EXPERIENCIA_BAJA = 3
EDAD_MINIMA_PARA_SUBIR = 17
DIAS_MINIMOS_EN_LA_ACADEMIA = 112
PARTIDOS_SIN_JUGAR = 2


@dataclass(frozen=True)
class Resistencia:
    ht_player_id: int
    name: str
    nivel: int
    esperado: int


def resistencia_baja_para_su_edad(jugadores: Sequence[Resistencia]) -> list[Insight]:
    """B1."""
    return [
        Insight(
            key=f"player.stamina_low.{j.ht_player_id}",
            severity=Severity.WARNING,
            title=f"{j.name} tiene la resistencia baja para su edad",
            detail=(
                f"Está en {j.nivel} y lo esperado con tu entrenamiento de resistencia es "
                f"{j.esperado}."
            ),
            action="Revisa el porcentaje de resistencia en Entrenamiento.",
            module="entrenamiento",
            evidence={"ht_player_id": j.ht_player_id, "level": j.nivel, "expected": j.esperado},
        )
        for j in jugadores
        if j.esperado - j.nivel >= NIVELES_DE_RESISTENCIA_BAJA
    ]


@dataclass(frozen=True)
class Titular:
    ht_player_id: int
    name: str
    en_venta: bool
    experiencia: int
    #: Cuándo jugó su último partido, de su ficha; None si no consta.
    ultimo_partido: datetime | None


def titular_en_venta(titulares: Sequence[Titular]) -> list[Insight]:
    """B2."""
    return [
        Insight(
            key=f"market.starter_listed.{t.ht_player_id}",
            severity=Severity.WARNING,
            title=f"Tienes en venta a {t.name}, que es titular",
            detail="Sale en el mejor once de las formaciones con más experiencia del equipo.",
            action="Si es a propósito, prepara su sustituto en Alineación.",
            module="transferencias",
            evidence={"ht_player_id": t.ht_player_id},
        )
        for t in titulares
        if t.en_venta
    ]


@dataclass(frozen=True)
class Venta:
    ht_player_id: int
    name: str
    #: Precio por comparables (media), en la moneda del equipo.
    precio: int | None
    gastos: float
    #: Fracción, no porcentaje: 0,1327 es el 13,27 %.
    comision_de_la_casa: float | None
    comision_de_reventa: float


def precio_de_equilibrio(v: Venta) -> int | None:
    """La misma cuenta que el simulador de venta de Transferencias."""
    if v.comision_de_la_casa is None or v.comision_de_la_casa >= 1:
        return None
    return math.ceil((v.gastos - v.comision_de_reventa) / (1 - v.comision_de_la_casa))


def venta_con_ganancia(ventas: Sequence[Venta], moneda: str) -> list[Insight]:
    """B3: lo que ha costado gente parecida ya supera su precio de equilibrio."""
    out = []
    for v in ventas:
        equilibrio = precio_de_equilibrio(v)
        if v.precio is None or equilibrio is None or v.gastos <= 0:
            continue
        if v.precio > equilibrio:
            out.append(
                Insight(
                    key=f"market.profitable_sale.{v.ht_player_id}",
                    severity=Severity.OPPORTUNITY,
                    title=f"Vender a {v.name} hoy dejaría ganancia",
                    detail=(
                        f"Jugadores parecidos se han vendido por {thousands(v.precio)} {moneda} "
                        f"de media y su precio de equilibrio es {thousands(equilibrio)} {moneda}."
                    ),
                    action="Simúlalo en Transferencias → Plantilla actual.",
                    module="transferencias",
                    # El nombre lleva a su Comparador de transferencias
                    # (2026-11-21, pedido del usuario).
                    evidence={
                        "ht_player_id": v.ht_player_id,
                        "name": v.name,
                        "enlace": "comparador",
                    },
                )
            )
    return out


def _titulo_del_cruce(c: Cruce) -> str:
    n = c.nombre
    if c.senal == "precio":
        if c.sentido == "sube":
            return f"{n} ya vale más que su precio de equilibrio"
        return f"{n} ya vale menos que su precio de equilibrio"
    if c.senal == "maximo":
        if c.sentido == "sube":
            return f"Ya se pagó por un parecido a {n} más que su precio de equilibrio"
        return f"Ya no se paga por un parecido a {n} más que su precio de equilibrio"
    return f"Una puja por un parecido a {n} supera su precio de equilibrio"


def _detalle_del_cruce(c: Cruce, moneda: str) -> str:
    """Una frase entera por caso: partida en trozos no se traduciría."""
    a, b = thousands(c.antes), thousands(c.ahora)
    ea, eb = thousands(c.equilibrio_antes), thousands(c.equilibrio_ahora)
    if c.senal == "precio":
        return (
            f"Su precio por comparables pasó de {a} a {b} {moneda} y su precio de "
            f"equilibrio, de {ea} a {eb} {moneda}."
        )
    if c.senal == "maximo":
        return (
            f"Lo máximo pagado por un parecido pasó de {a} a {b} {moneda} y su precio de "
            f"equilibrio, de {ea} a {eb} {moneda}."
        )
    return f"La puja más alta abierta es de {b} {moneda}; su precio de equilibrio es {eb} {moneda}."


def cruces_del_equilibrio(cruces: Sequence[Cruce], moneda: str) -> list[Insight]:
    """Un aviso por cada precio que cruzó el precio de equilibrio de un
    jugador desde la sincronización anterior (2026-11-21, pedido del usuario).
    Hacia arriba es una oportunidad de vender sin pérdida; hacia abajo, que esa
    ventana se cerró."""
    return [
        Insight(
            key=f"market.breakeven_cross.{c.ht_player_id}.{c.senal}.{c.sentido}",
            severity=Severity.OPPORTUNITY if c.sentido == "sube" else Severity.WARNING,
            title=_titulo_del_cruce(c),
            detail=_detalle_del_cruce(c, moneda),
            action="Míralo en su Comparador de transferencias.",
            module="transferencias",
            evidence={"ht_player_id": c.ht_player_id, "name": c.nombre, "enlace": "comparador"},
        )
        for c in cruces
    ]


@dataclass(frozen=True)
class PrecioSemanal:
    ht_player_id: int
    name: str
    antes: int
    ahora: int


def precio_que_sube(precios: Sequence[PrecioSemanal]) -> list[Insight]:
    """B4: el precio por comparables sube un 15 % o más en una semana."""
    return [
        Insight(
            key=f"market.price_rising.{p.ht_player_id}",
            severity=Severity.OPPORTUNITY,
            title=f"El precio de {p.name} sube un {p.ahora / p.antes - 1:.0%} en una semana",
            detail="Es lo que han costado jugadores parecidos, comparado con hace siete días.",
            module="transferencias",
            evidence={"ht_player_id": p.ht_player_id},
        )
        for p in precios
        if p.antes > 0 and p.ahora * 100 >= p.antes * (100 + SUBIDA_DE_PRECIO_PCT)
    ]


@dataclass(frozen=True)
class Reventa:
    ht_player_id: int
    name: str
    cierra: datetime
    #: Lo que nos toca de su venta, si se sabe cuántos partidos jugó.
    porcentaje: float | None


def _detalle_de_la_reventa(r: Reventa) -> str:
    # Cada variante es UNA frase entera: el traductor reconoce plantillas
    # completas, y dos trozos pegados no casarían con ninguna.
    cierre = r.cierra.strftime("%d/%m %H:%M")
    if r.porcentaje is None:
        return (
            "Si se vende, te toca comisión como club anterior. "
            f"La subasta cierra el {cierre} (UTC)."
        )
    pct = f"{r.porcentaje:.1%}"
    return f"Si se vende, te toca el {pct} como club anterior. La subasta cierra el {cierre} (UTC)."


def comision_a_la_vista(reventas: Sequence[Reventa], ahora: datetime) -> list[Insight]:
    """B5: un ex jugador tuyo está en venta y su traspaso te daría comisión."""
    return [
        Insight(
            key=f"market.resale_ahead.{r.ht_player_id}",
            severity=Severity.OPPORTUNITY,
            title=f"Tu ex jugador {r.name} está en venta",
            detail=_detalle_de_la_reventa(r),
            action="La app la anotará sola en la siguiente sincronización tras el cierre.",
            module="transferencias",
            evidence={"ht_player_id": r.ht_player_id},
        )
        for r in reventas
        if r.cierra > ahora
    ]


def titular_sin_experiencia(titulares: Sequence[Titular]) -> list[Insight]:
    """B9: 3 niveles o más por debajo de la media del once."""
    if len(titulares) < 2:
        return []
    media = sum(t.experiencia for t in titulares) / len(titulares)
    return [
        Insight(
            key=f"player.inexperienced_starter.{t.ht_player_id}",
            severity=Severity.WARNING,
            title=f"{t.name} es titular con poca experiencia",
            detail=f"Tiene {t.experiencia} y la media de los titulares es {media:.1f}.",
            action="Dale minutos en amistosos o tenlo en cuenta en partidos importantes.",
            module="alineación",
            evidence={"ht_player_id": t.ht_player_id},
        )
        for t in titulares
        if media - t.experiencia >= NIVELES_DE_EXPERIENCIA_BAJA
    ]


@dataclass(frozen=True)
class Juvenil:
    ht_youth_player_id: int
    name: str
    age_years: int
    age_days: int
    dias_en_la_academia: int | None


def juvenil_listo_para_subir(juveniles: Sequence[Juvenil]) -> list[Insight]:
    """B12: 17 años y 0 días o más, y al menos 112 días en la academia."""
    return [
        Insight(
            key=f"academy.ready_to_promote.{y.ht_youth_player_id}",
            severity=Severity.OPPORTUNITY,
            title=f"{y.name} ya puede subir al primer equipo",
            detail=(
                f"Tiene {y.age_years} años y {y.age_days} días y lleva "
                f"{y.dias_en_la_academia} días en la academia."
            ),
            action="Decide en Juveniles si lo subes o esperas.",
            module="academia",
            evidence={"ht_youth_player_id": y.ht_youth_player_id},
        )
        for y in juveniles
        if y.age_years >= EDAD_MINIMA_PARA_SUBIR
        and y.dias_en_la_academia is not None
        and y.dias_en_la_academia >= DIAS_MINIMOS_EN_LA_ACADEMIA
    ]


def titular_que_no_juega(
    titulares: Sequence[Titular], ultimos_oficiales: Sequence[datetime]
) -> list[Insight]:
    """B14: un Titular no jugó ninguno de los 2 últimos partidos oficiales.

    `ultimos_oficiales`: las fechas de los partidos oficiales ya jugados, de la
    más reciente a la más vieja."""
    if len(ultimos_oficiales) < PARTIDOS_SIN_JUGAR:
        return []
    desde = ultimos_oficiales[PARTIDOS_SIN_JUGAR - 1]
    return [
        Insight(
            key=f"player.starter_not_playing.{t.ht_player_id}",
            severity=Severity.WARNING,
            title=(
                f"{t.name} es titular y no jugó los {PARTIDOS_SIN_JUGAR} últimos partidos oficiales"
            ),
            detail="La app lo pone en el mejor once, pero se está quedando fuera.",
            action="Revisa la alineación, o si hay un motivo (lesión, sanción).",
            module="alineación",
            evidence={"ht_player_id": t.ht_player_id},
        )
        for t in titulares
        if t.ultimo_partido is None or t.ultimo_partido < desde
    ]
