"""Hora de Hattrick → UTC.

CHPP entrega TODAS sus fechas en la hora del servidor de Hattrick, que es la
hora sueca (CET en invierno, CEST en verano), y las escribe sin marca de zona:
``2026-08-20 00:10:00``.

Hasta 2026-08-16 el sync hacía ``.replace(tzinfo=UTC)`` sobre esa cadena, que
NO convierte: se limita a etiquetar como UTC una hora que no lo es. El partido
de Copa del miércoles 19 a las 17:10 en Colombia se guardaba como las 00:10 del
jueves 20 y así se mostraba — siete horas de más, que es exactamente CEST menos
la hora colombiana.

El desfase no es constante: son +1 en invierno y +2 en verano, y el cambio no
cae el mismo día cada año. Por eso se resuelve con la base de datos de zonas
horarias y nunca con una constante.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# Hattrick corre en hora sueca. Estocolmo y no "CET" a secas porque `ZoneInfo`
# necesita la zona real para saber cuándo aplica el horario de verano.
HATTRICK_TZ = ZoneInfo("Europe/Stockholm")


def ht_to_utc(value: str | None) -> datetime | None:
    """Fecha de CHPP a `datetime` real en UTC, o `None` si viene vacía o rota.

    El valor de entrada es hora de Hattrick sin zona; aquí se le pone la zona
    que de verdad le corresponde y se convierte.
    """
    if not value:
        return None
    try:
        naive = datetime.fromisoformat(value)
    except ValueError:
        return None
    if naive.tzinfo is not None:
        return naive.astimezone(UTC)
    return naive.replace(tzinfo=HATTRICK_TZ).astimezone(UTC)


def ht_to_utc_naive(value: str | None) -> datetime | None:
    """Igual que `ht_to_utc` pero sin `tzinfo`.

    Hace falta donde el valor se compara contra una columna leída de sqlite,
    que siempre vuelve naive: mezclar aware y naive revienta con TypeError.
    """
    converted = ht_to_utc(value)
    return converted.replace(tzinfo=None) if converted is not None else None


def ht_day(value: datetime | None) -> date | None:
    """El día del CALENDARIO de Hattrick al que pertenece un instante.

    "Hoy" y "mañana" —los dos únicos días que Hattrick pronostica— son días
    suecos, no días del usuario ni días UTC. Un partido de las 19:00 en
    Colombia cae en el día siguiente sueco, y sin esta conversión el
    pronóstico de "mañana" se leería como el de hoy.
    """
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(HATTRICK_TZ).date()
