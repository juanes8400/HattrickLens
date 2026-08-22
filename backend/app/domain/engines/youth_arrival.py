"""Cuándo pudo llegar, como muy pronto, un canterano al primer equipo.

Un jugador de tu cantera no se compra, así que no tiene fecha de compra. Y sin
un principio de etapa no hay forma de recorrer sus partidos: el censo se
saltaba a la mitad de los canteranos vendidos, que son justamente aquellos de
los que más importa saberlo, porque un canterano cobra comisión en TODAS sus
ventas futuras y ese porcentaje sale del número de partidos.

La idea, del usuario: en Hattrick nadie llega al primer equipo antes de los 17
años, así que la fecha en que cumplió 17 años y 0 días es un SUELO. Como muy
pronto, llegó ese día. Buscar desde ahí puede cubrir de más, nunca de menos,
así que el conteo resultante no puede quedarse corto.

La edad en Hattrick avanza un día por cada día real, así que ese suelo no es
una estimación: se calcula exacto restando los días que le sobraban sobre
17.000 en una fecha en la que sí se conoce su edad.

Esto es fontanería del recorrido, no un dato del jugador: la fecha no se
guarda como su llegada ni se enseña en su ficha.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.value_objects.skill import Age

EDAD_MINIMA_PRIMER_EQUIPO = 17


@dataclass(frozen=True)
class LlegadaMasTemprana:
    """El suelo, con su semana de Hattrick al lado."""

    fecha: datetime
    #: "83-05" si se pudo situar en el calendario; `None` si falta el contexto
    #: del país para traducir la fecha a temporada y semana.
    semana: str | None


def dias_desde_los_diecisiete(edad: Age) -> int:
    """Cuántos días lleva cumplidos por encima de los 17 años exactos.

    Negativo si aún no los tiene, que en el primer equipo no debería pasar.
    """
    return (
        edad.years * Age.DAYS_PER_YEAR
        + edad.days
        - EDAD_MINIMA_PRIMER_EQUIPO * Age.DAYS_PER_YEAR
    )


def cuando_cumplio_diecisiete(edad_en: Age, fecha: datetime) -> datetime:
    """La fecha real en que ese jugador cumplió 17 años y 0 días.

    `edad_en` es su edad en `fecha`, de donde se cuenta hacia atrás.
    """
    return fecha - timedelta(days=dias_desde_los_diecisiete(edad_en))


def llegada_mas_temprana(
    edad_en: Age,
    fecha: datetime,
    semana_de: "object | None" = None,
) -> LlegadaMasTemprana:
    """El suelo del recorrido, listo para usar.

    `semana_de` es una función que traduce una fecha a "temporada-semana"; se
    recibe de fuera para que este motor no dependa de la base de datos.
    """
    cuando = cuando_cumplio_diecisiete(edad_en, fecha)
    semana = semana_de(cuando) if callable(semana_de) else None
    return LlegadaMasTemprana(fecha=cuando, semana=semana)
