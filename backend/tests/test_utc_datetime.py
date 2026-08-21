"""Las fechas llegan a Python siempre igual, venga de donde venga.

2026-08-20, con la app ya publicada: usuarios reales reportaron que
Transferencias y Juveniles no cargaban. En local no fallaba nunca.

La app entera está escrita sobre fechas INGENUAS en UTC, porque es lo que
devuelve sqlite, que es donde se desarrolló y se probó todo. Postgres devuelve
`timestamptz` CON zona, y `player_balance.weeks_owned` resta esa fecha contra
un `datetime.now(UTC).replace(tzinfo=None)`:

    TypeError: can't subtract offset-naive and offset-aware datetimes

Cuatro rutas caían por ahí (saldo por jugador, juveniles y las dos de alertas,
que lo llaman por dentro), y solo para los equipos con algún jugador comprado
— de ahí que unos usuarios lo vieran y otros no.

`UtcDateTime` lo normaliza en la frontera. Estos tests fijan las dos mitades.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects import postgresql, sqlite

from app.domain.engines.player_balance import weeks_owned
from app.infrastructure.db.models import UtcDateTime

CON_ZONA = datetime(2026, 8, 20, 15, 30, tzinfo=UTC)
SIN_ZONA = datetime(2026, 8, 20, 15, 30)


def test_a_date_read_from_postgres_arrives_without_timezone() -> None:
    tipo = UtcDateTime()
    assert tipo.process_result_value(CON_ZONA, postgresql.dialect()) == SIN_ZONA
    # Y lo que ya viene ingenuo (sqlite) se queda como está.
    assert tipo.process_result_value(SIN_ZONA, sqlite.dialect()) == SIN_ZONA
    assert tipo.process_result_value(None, postgresql.dialect()) is None


def test_a_date_written_to_each_engine_goes_in_the_form_it_accepts() -> None:
    tipo = UtcDateTime()
    # Postgres guarda `timestamptz`: la fecha va con zona, siempre UTC.
    guardada = tipo.process_bind_param(SIN_ZONA, postgresql.dialect())
    assert guardada is not None and guardada.tzinfo is not None
    assert guardada.utcoffset() == timedelta(0)
    # sqlite guarda texto sin desfase: una fecha con zona lo rompería.
    assert tipo.process_bind_param(CON_ZONA, sqlite.dialect()) == SIN_ZONA


def test_the_subtraction_that_broke_transfers_and_youth_works_again() -> None:
    """El cálculo exacto que reventaba: semanas desde la compra."""
    comprado = UtcDateTime().process_result_value(
        datetime(2026, 6, 20, 12, 0, tzinfo=UTC), postgresql.dialect()
    )
    ahora = datetime.now(UTC).replace(tzinfo=None)
    assert comprado is not None
    assert weeks_owned(comprado, ahora) >= 0
