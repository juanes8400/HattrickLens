"""Un once a medias se cuenta, y el aviso lo dice en cristiano.

EL CASO REAL, 2026-10-07. Amistoso internacional 771779994, Pulgas Arrechas
contra Kaffegokarna. Las ordenes se descargaban bien --diez posiciones-- pero
la llamada de ratings previstos volvia con `chpperror.xml` diciendo

    Sequence contains no matching element

que es una excepcion de .NET escapandose del servidor de Hattrick. No dice
que pasa ni que hacer, y el usuario la veia tal cual en su sincronizacion.

La causa era que el once tenia DIEZ jugadores en el campo. Los puestos que
llegaron fueron 100..108 y 110: Hattrick OMITE los vacios en vez de mandarlos
con el jugador a cero, asi que el hueco solo se ve contando.

Y por eso el aviso habla del NUMERO y no del puesto. Los identificadores que
faltan pueden ser los que esa formacion no usa, asi que decir «falta el
mediocentro izquierdo» seria adivinar.
"""

from app.application.commands.sync_team.alineacion import (
    TITULARES,
    _cubiertos_en_el_campo,
)
from app.i18n.traductor import Traductor

#: Tal como lo mando Hattrick aquel dia: diez puestos, sin el 109.
EL_ONCE_DE_AQUEL_DIA = [
    {"role_id": 100, "ht_player_id": 444563841, "behaviour": 0},
    {"role_id": 101, "ht_player_id": 490465993, "behaviour": 0},
    {"role_id": 102, "ht_player_id": 498724298, "behaviour": 0},
    {"role_id": 103, "ht_player_id": 479881607, "behaviour": 0},
    {"role_id": 104, "ht_player_id": 493068717, "behaviour": 0},
    {"role_id": 105, "ht_player_id": 495010544, "behaviour": 0},
    {"role_id": 106, "ht_player_id": 497733329, "behaviour": 0},
    {"role_id": 107, "ht_player_id": 492851039, "behaviour": 0},
    {"role_id": 108, "ht_player_id": 493777217, "behaviour": 0},
    {"role_id": 110, "ht_player_id": 461351045, "behaviour": 0},
]


def test_el_once_de_aquel_dia_tenia_diez() -> None:
    assert _cubiertos_en_el_campo(EL_ONCE_DE_AQUEL_DIA) == 10
    assert _cubiertos_en_el_campo(EL_ONCE_DE_AQUEL_DIA) < TITULARES


def test_un_once_completo_no_dispara_el_aviso() -> None:
    """Once puestos cubiertos: lo que falle sera otra cosa, y entonces el
    mensaje de Hattrick se deja tal cual porque no sabemos traducirlo."""
    completo = [*EL_ONCE_DE_AQUEL_DIA, {"role_id": 109, "ht_player_id": 999, "behaviour": 0}]
    assert _cubiertos_en_el_campo(completo) == TITULARES


def test_el_banquillo_no_cuenta_como_titular() -> None:
    """Del 114 en adelante son suplentes. Sumarlos daria un once completo
    con el campo a medias, que es justo el fallo que esto evita."""
    con_banquillo = [
        *EL_ONCE_DE_AQUEL_DIA,
        {"role_id": 114, "ht_player_id": 111, "behaviour": 0},
        {"role_id": 115, "ht_player_id": 222, "behaviour": 0},
    ]
    assert _cubiertos_en_el_campo(con_banquillo) == 10


def test_un_puesto_sin_jugador_no_cuenta() -> None:
    """Por si algun dia Hattrick manda el hueco en vez de omitirlo."""
    con_vacio = [
        *EL_ONCE_DE_AQUEL_DIA,
        {"role_id": 109, "ht_player_id": 0, "behaviour": 0},
    ]
    assert _cubiertos_en_el_campo(con_vacio) == 10


def test_lo_que_no_sea_una_lista_de_puestos_no_revienta() -> None:
    """Viene de CHPP: puede llegar cualquier cosa."""
    assert _cubiertos_en_el_campo(None) == 0
    assert _cubiertos_en_el_campo("positions") == 0
    assert _cubiertos_en_el_campo([{"role_id": "x", "ht_player_id": "y"}, 7, None]) == 0


def test_el_aviso_se_traduce_entero_con_su_fuente_dentro() -> None:
    """La plantilla lleva tres huecos, y el traductor traduce TAMBIEN lo que
    captura: el nombre de la fuente entra en el primero y tiene que salir en
    ingles, no «alineación y órdenes enviadas» dentro de una frase inglesa."""
    traductor = Traductor(
        {
            "alineación y órdenes enviadas": "lineup and orders submitted",
            (
                "{} ({}): tu alineación tiene {} jugadores y hacen falta once, "
                "así que Hattrick no puede calcular los ratings"
            ): (
                "{} ({}): your lineup has {} players and eleven are needed, "
                "so Hattrick cannot calculate the ratings"
            ),
        }
    )
    dicho = (
        "alineación y órdenes enviadas (771779994): tu alineación tiene 10 jugadores "
        "y hacen falta once, así que Hattrick no puede calcular los ratings"
    )
    assert traductor.texto(dicho) == (
        "lineup and orders submitted (771779994): your lineup has 10 players "
        "and eleven are needed, so Hattrick cannot calculate the ratings"
    )
