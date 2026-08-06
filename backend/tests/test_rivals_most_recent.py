"""`_most_recent_by_date` — HL-2xx: prueba directa de "más recientes, no
más antiguos", sin CHPP, sesión ni DB de por medio."""
from app.api.v1.endpoints.rivals import _most_recent_by_date


def test_keeps_the_most_recent_n_not_the_oldest() -> None:
    items = [
        {"id": "old", "match_date": "2026-06-01"},
        {"id": "a", "match_date": "2026-07-10"},
        {"id": "b", "match_date": "2026-07-12"},
        {"id": "c", "match_date": "2026-07-15"},
        {"id": "d", "match_date": "2026-07-18"},
        {"id": "e", "match_date": "2026-07-20"},
    ]
    out = _most_recent_by_date(items, "match_date", 5)
    ids = [it["id"] for it in out]
    assert "old" not in ids  # el más antiguo de los 6 queda fuera
    assert ids == ["a", "b", "c", "d", "e"]  # orden ascendente conservado


def test_returns_all_when_fewer_than_limit() -> None:
    items = [{"match_date": "2026-07-01"}, {"match_date": "2026-07-02"}]
    assert _most_recent_by_date(items, "match_date", 5) == items


def test_empty_input() -> None:
    assert _most_recent_by_date([], "match_date", 5) == []


def test_zero_limit_returns_empty() -> None:
    items = [{"match_date": "2026-07-01"}]
    assert _most_recent_by_date(items, "match_date", 0) == []
