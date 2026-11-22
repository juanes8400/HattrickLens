"""Los cruces del precio de equilibrio (2026-11-21, definidos por el usuario)."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.domain.engines.alertas_de_plantilla import cruces_del_equilibrio
from app.domain.engines.cruces_de_equilibrio import (
    Cruce,
    historia_de_pujas,
    puja_en,
    sentido_del_cruce,
)
from app.domain.engines.insights import KNOWN_KEY_ROOTS, Severity

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def test_el_precio_que_pasa_de_debajo_a_encima_sube() -> None:
    assert sentido_del_cruce(486, 498, 520, 505) == "sube"
    assert sentido_del_cruce(520, 505, 486, 498) == "baja"


def test_seguir_del_mismo_lado_no_es_un_cruce() -> None:
    assert sentido_del_cruce(400, 500, 450, 505) is None
    assert sentido_del_cruce(600, 500, 650, 505) is None


def test_cuenta_el_cruce_que_provoca_el_umbral_solo() -> None:
    """Decisión del usuario: el precio quieto y el sueldo subiendo el umbral
    también es un cruce."""
    assert sentido_del_cruce(312, 309, 312, 316) == "baja"


def test_llegar_justo_al_equilibrio_es_no_perder() -> None:
    assert sentido_del_cruce(499, 500, 500, 500) == "sube"


def test_la_puja_solo_avisa_al_subir() -> None:
    assert sentido_del_cruce(0, 500, 620, 500, solo_subida=True) == "sube"
    assert sentido_del_cruce(620, 500, 450, 500, solo_subida=True) is None


def test_sin_dato_no_hay_cruce() -> None:
    assert sentido_del_cruce(None, 500, 620, 500) is None
    assert sentido_del_cruce(400, None, 620, 500) is None


def test_la_historia_de_pujas_guarda_solo_los_cambios() -> None:
    h = historia_de_pujas(None, puja_anterior=None, visto_antes=None, puja=100, ahora=T0)
    h = historia_de_pujas(h, puja_anterior=100, visto_antes=T0, puja=100, ahora=T0 + timedelta(1))
    h = historia_de_pujas(h, puja_anterior=100, visto_antes=T0, puja=150, ahora=T0 + timedelta(2))
    assert [p for _, p in json.loads(h)] == [100, 150]
    assert puja_en(h, T0 - timedelta(1)) is None
    assert puja_en(h, T0 + timedelta(1)) == 100
    assert puja_en(h, T0 + timedelta(3)) == 150


def test_un_anuncio_de_antes_de_la_historia_arranca_con_lo_ultimo_visto() -> None:
    """Sin esto, la puja de antes sería cero y el aviso saltaría sin motivo
    la primera vez."""
    h = historia_de_pujas(
        "[]", puja_anterior=600, visto_antes=T0, puja=600, ahora=T0 + timedelta(1)
    )
    assert puja_en(h, T0 + timedelta(hours=12)) == 600


def test_las_alertas_dicen_que_cruzo_y_enlazan_al_comparador() -> None:
    cruce = Cruce(
        ht_player_id=7,
        nombre="Tommy Vidal",
        senal="precio",
        sentido="sube",
        antes=486_000,
        ahora=520_000,
        equilibrio_antes=498_000,
        equilibrio_ahora=505_000,
    )
    (alerta,) = cruces_del_equilibrio([cruce], "COP")
    assert alerta.severity == Severity.OPPORTUNITY
    assert alerta.title == "Tommy Vidal ya vale más que su precio de equilibrio"
    assert alerta.detail == "Vale 520.000 COP. Para no perder necesitas 505.000 COP."
    assert alerta.evidence == {"ht_player_id": 7, "name": "Tommy Vidal", "enlace": "comparador"}
    assert alerta.key.startswith("market.breakeven_cross.")
    assert "market.breakeven_cross" in KNOWN_KEY_ROOTS
    (baja,) = cruces_del_equilibrio([replace(cruce, sentido="baja")], "COP")
    assert baja.severity == Severity.WARNING


def test_las_frases_de_lo_mas_pagado_y_de_la_puja() -> None:
    """Las del estilo «A» que eligió el usuario el 2026-11-22."""
    cruce = Cruce(
        ht_player_id=7,
        nombre="Tommy Vidal",
        senal="maximo",
        sentido="sube",
        antes=486_000,
        ahora=530_000,
        equilibrio_antes=498_000,
        equilibrio_ahora=505_000,
    )
    (sube,) = cruces_del_equilibrio([cruce], "COP")
    assert sube.title == (
        "Alguien pagó por un jugador como Tommy Vidal más que su precio de equilibrio"
    )
    assert sube.detail == "Lo más pagado es 530.000 COP. Para no perder necesitas 505.000 COP."
    (baja,) = cruces_del_equilibrio([replace(cruce, sentido="baja")], "COP")
    assert baja.title == (
        "Lo más pagado por un jugador como Tommy Vidal ya no llega a su precio de equilibrio"
    )
    (puja,) = cruces_del_equilibrio([replace(cruce, senal="puja")], "COP")
    assert puja.title == (
        "Hay una puja por un jugador como Tommy Vidal más alta que su precio de equilibrio"
    )
    assert puja.detail == "La puja va en 530.000 COP. Para no perder necesitas 505.000 COP."
