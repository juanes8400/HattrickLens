from app.domain.value_objects.ht_constants import match_role_short_label


def test_match_role_short_label_drops_the_side_but_keeps_the_order() -> None:
    """2026-08-09, pedido explícitamente: el lado (derecho/izquierdo/medio)
    no importa para "Última semana", pero la orden individual real
    (Ofensivo/Defensivo/Hacia el medio/Hacia la banda) sí — ese dato vive
    en `Behaviour` de matchlineup.xml, no en `PositionCode`."""
    assert match_role_short_label(100, 0) == "Portero"
    assert match_role_short_label(101, 0) == "DL"  # lateral derecho
    assert match_role_short_label(105, 0) == "DL"  # lateral izquierdo — mismo DL
    assert match_role_short_label(102, 1) == "DC of"
    assert match_role_short_label(103, 2) == "DC def"
    assert match_role_short_label(104, 3) == "DC h M"
    assert match_role_short_label(106, 4) == "Ex h L"
    assert match_role_short_label(108, 0) == "Medio"
    assert match_role_short_label(111, 1) == "Del of"


def test_match_role_short_label_hides_extra_and_no_change_behaviours() -> None:
    """Behaviour 5/6/7 (delantero/interior/defensa extra) marca un cupo de
    suplente, no una orden elegida — pedido explícitamente: no debe llevar
    sufijo, igual que "Normal" (0) o "Sin cambio" (-1)."""
    assert match_role_short_label(111, 5) == "Del"
    assert match_role_short_label(108, 6) == "Medio"
    assert match_role_short_label(102, 7) == "DC"
    assert match_role_short_label(102, -1) == "DC"
    assert match_role_short_label(102, None) == "DC"


def test_match_role_short_label_falls_back_for_an_unknown_role() -> None:
    assert match_role_short_label(999, 1) == "posición 999 (sin traducir)"
