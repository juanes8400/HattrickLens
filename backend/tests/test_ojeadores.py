"""Lo que dijo el ojeador que trajo a cada canterano.

El fixture es real: Alirio Asprilla (424402061), pedido el 2026-08-24. No
existe un fichero de ojeadores en CHPP --`youthscouts`, `youthscoutlist` y
`scouts` devuelven 401--, asi que `youthplayerdetails.xml` es la unica via.
"""
from pathlib import Path

from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).parent / "fixtures"


def _ficha() -> dict:
    return get_parser("youthplayerdetails")(
        (FIXTURES / "youthplayerdetails.xml").read_bytes()
    )


def test_quien_lo_trajo_y_de_donde() -> None:
    d = _ficha()
    assert d["ht_youth_player_id"] == 424402061
    assert d["scout_id"] == 10768192
    assert d["scout_name"] == "Mauricio Guerra"
    assert d["scouting_region_id"] == 1717


def test_los_comentarios_llegan_enteros_y_sin_entidades() -> None:
    """El texto trae `&nbsp;` pegado al final; en pantalla eso se ve."""
    comentarios = _ficha()["scout_comments"]
    assert len(comentarios) == 3
    assert all("&nbsp;" not in c["text"] for c in comentarios)
    assert all(c["text"] for c in comentarios)


def test_el_comentario_de_nivel_y_el_de_potencial_dicen_la_misma_habilidad() -> None:
    """Tipo 4 = "tiene nivel X"; tipo 5 = "alcanzara un potencial Z"."""
    porque = {c["type"]: c for c in _ficha()["scout_comments"]}
    assert porque[4]["skill"] == "passing"
    assert porque[4]["level"] == 5
    assert porque[5]["skill"] == "passing"
    assert porque[5]["level"] == 6


def test_el_comentario_de_presentacion_no_habla_de_una_habilidad() -> None:
    """En el tipo 1, `CommentSkillType` trae el ID del jugador. Traducirlo a
    una habilidad seria inventar un dato que nadie dijo."""
    presentacion = next(c for c in _ficha()["scout_comments"] if c["type"] == 1)
    assert presentacion["skill"] is None
    assert presentacion["skill_code"] == 424402061


def test_may_unlock_dice_que_queda_por_revelar() -> None:
    """Es la respuesta exacta a "que me falta por saber de el", que hasta
    ahora solo se podia suponer."""
    puede = _ficha()["may_unlock"]
    assert set(puede) == {
        "keeper", "defending", "playmaking", "winger",
        "passing", "scoring", "set_pieces",
    }
    # Pases ya esta revelado del todo: no queda nada que desbloquear ahi.
    assert puede["passing"] is False
    assert isinstance(puede["defending"], bool)
