"""El anuncio sin pujas: se guarda, no vale como precio, y se borra si no fue.

2026-11-07. El usuario encontró el agujero por su nombre:

    «472301981, este jugador debió haber entrado al comparador. Posible
    explicación: no lo tomó porque no tuvo puja sino hasta el final, y ya entre
    puja final y el jugador siendo un desconocido, no hubo sincronización.
    Posible solución: buscar todos los jugadores que estén en el mercado, así
    sea en 0, y guardarlos para el futuro, descartarlos si al final no se
    vendieron. Guardar el precio inicial, para analizar la relación entre
    precio inicial, final y horario.»

Aquí se defienden las tres mitades de esa decisión: que entran, que entrar no
los convierte en un precio, y que el que no se vendió se va.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    SIN_PUJA_QUE_SE_ENSENAN,
    Guardado,
    Objetivo,
    Rasgo,
    comparables_de,
    cuenta_para_el_numero,
    estimar,
    nunca_tuvo_puja,
    objetivo_de,
    ocupa_plaza,
    se_puede_descartar,
)

AHORA = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)

#: Las siete habilidades de un delantero cualquiera. Da igual cuáles sean:
#: lo que se mide aquí es qué hace el motor con un anuncio a cero, y para eso
#: hace falta que el anuncio SE PAREZCA, que es lo único que decide si entra.
HABILIDADES = {
    "keeper": 1,
    "defending": 4,
    "playmaking": 7,
    "winger": 5,
    "passing": 13,
    "scoring": 18,
    "setpieces": 3,
}


def _objetivo() -> Objetivo:
    objetivo = objetivo_de(ht_player_id=999, edad=31, skills=HABILIDADES)
    assert objetivo is not None
    return objetivo


def _venta(
    ident: int,
    *,
    puja: int = 50_000,
    precio: int | None = None,
    firme: bool = False,
    intentos: int = 0,
    pedido: int = 0,
) -> Guardado:
    """Una venta clavada al objetivo, para que el parecido no estorbe."""
    return Guardado(
        ht_player_id=ident,
        nombre=f"Jugador {ident}",
        precio=puja if precio is None else precio,
        firme=firme,
        puja=puja,
        visto_el=AHORA - timedelta(days=1),
        edad=31,
        dias=10,
        primaria=Rasgo("scoring", 18),
        secundaria=Rasgo("passing", 13),
        terciaria=Rasgo("playmaking", 7),
        habilidades=dict(HABILIDADES),
        especialidad=0,
        tsi=150_000,
        forma=6,
        precio_pedido=pedido,
        plazo=AHORA - timedelta(hours=5),
        intentos=intentos,
    )


# --------------------------------------------------------------------------
# Entrar no es contar
# --------------------------------------------------------------------------


def test_un_anuncio_a_cero_no_ocupa_plaza_ni_cuenta() -> None:
    """Es lo que permite guardarlos sin mover un solo número.

    Si ocupara plaza, ocho anuncios muertos darían el fondo por lleno y el
    barrido dejaría de salir a buscar lo que de verdad falta --el caso de Kurt
    Schönhueb--. Si contara, su cero arrastraría la media a la mitad.
    """
    cero = _venta(1, puja=0, precio=0)
    assert nunca_tuvo_puja(cero) is True
    assert ocupa_plaza(cero) is False
    assert cuenta_para_el_numero(cero) is False
    assert estimar(comparables_de([cero], _objetivo(), AHORA)).media is None


def test_la_venta_cerrada_sin_puja_vista_SI_cuenta() -> None:
    """ES EL CASO QUE SE VINO A BUSCAR, y la razón de todo el cambio.

    El 472301981 se vendió de verdad. Lo único que pasó es que su subasta se
    movió entre dos barridos nuestros, así que nunca le vimos puja. Esa venta
    es un precio real pagado por alguien parecido: el mejor dato que existe.
    """
    vendido = _venta(1, puja=0, precio=1_241_000, firme=True)
    assert nunca_tuvo_puja(vendido) is True
    assert cuenta_para_el_numero(vendido) is True
    assert ocupa_plaza(vendido) is True
    assert estimar(comparables_de([vendido], _objetivo(), AHORA)).media == 1_241_000


# --------------------------------------------------------------------------
# El tope de la tabla
# --------------------------------------------------------------------------


def test_los_anuncios_muertos_tienen_tope_y_los_buenos_no() -> None:
    """Sin tope la tabla se hunde, y con tope los de verdad siguen enteros.

    El barrido es diario y cada pasada trae decenas de anuncios parecidos a
    alguien de la plantilla. Guardados todos, en siete semanas la tabla de un
    jugador serían cientos de filas muertas por delante de sus comparables.
    """
    buenas = [_venta(i, precio=800_000 + i, firme=True) for i in range(1, OBJETIVO + 1)]
    muertos = [_venta(100 + i, puja=0, precio=0) for i in range(40)]
    salen = comparables_de([*buenas, *muertos], _objetivo(), AHORA)
    # Las ocho de verdad, enteras, y como mucho ocho muertas detrás.
    assert sum(1 for c in salen if c.cuenta) == OBJETIVO
    assert sum(1 for c in salen if nunca_tuvo_puja(c.venta)) == SIN_PUJA_QUE_SE_ENSENAN
    # Y van DETRÁS: lo que cuenta se lee primero.
    posiciones = [i for i, c in enumerate(salen) if nunca_tuvo_puja(c.venta)]
    assert min(posiciones) >= OBJETIVO


def test_una_puja_abandonada_no_lleva_tope() -> None:
    """Son pocas y cada una conserva un dato: alguien ofreció ese dinero por
    alguien así. El tope es sólo para los que nunca tuvieron nada."""
    abandonadas = [_venta(i, puja=5_000, intentos=99) for i in range(1, 31)]
    salen = comparables_de(abandonadas, _objetivo(), AHORA)
    assert len(salen) == 30
    assert not any(c.ocupa for c in salen)


# --------------------------------------------------------------------------
# Descartar lo que no se vendió
# --------------------------------------------------------------------------


def test_se_descarta_el_que_agoto_intentos_sin_venderse() -> None:
    muerto = _venta(1, puja=0, precio=0, intentos=99)
    assert se_puede_descartar(muerto) is True


def test_no_se_descarta_mientras_le_queden_intentos() -> None:
    """Ahí está justo la gracia: puede estar a punto de recibir su primera
    puja, que es lo que le pasó al 472301981."""
    vivo = _venta(1, puja=0, precio=0, intentos=0)
    assert se_puede_descartar(vivo) is False


def test_no_se_descarta_nunca_una_venta_firme() -> None:
    vendido = _venta(1, puja=0, precio=1_241_000, firme=True, intentos=99)
    assert se_puede_descartar(vendido) is False


def test_no_se_descarta_una_puja_abandonada() -> None:
    """Conserva un dato y se queda marcada como provisional abandonada; el
    borrado es sólo para el anuncio que nunca tuvo nada."""
    con_puja = _venta(1, puja=5_000, intentos=99)
    assert se_puede_descartar(con_puja) is False


# --------------------------------------------------------------------------
# El precio pedido
# --------------------------------------------------------------------------


def test_el_precio_pedido_viaja_y_no_es_el_precio() -> None:
    """«Guardar el precio inicial, para analizar la relación entre precio
    inicial, final y horario.»

    Se guarda aparte a propósito: un precio pedido es lo que una persona
    decidió pedir, así que no puede entrar en una media. Lo que sí puede es
    ponerse al lado del cierre, y la distancia entre los dos es el dato.
    """
    vendido = _venta(1, puja=0, precio=1_241_000, firme=True, pedido=2_000_000)
    assert vendido.precio_pedido == 2_000_000
    # No tocó el número: la media es el precio de cierre, no lo que se pedía.
    assert estimar(comparables_de([vendido], _objetivo(), AHORA)).media == 1_241_000


def test_la_forma_viaja_y_no_decide_el_parecido() -> None:
    """Es columna del Comparador de Transferencias, y el usuario la pidió. Pero
    el parecido se mide por habilidades, que es lo que él decidió el
    2026-10-06; que dos jugadores estén en forma distinta no los hace menos
    comparables."""
    en_forma = _venta(1, precio=900_000, firme=True)
    hundido = replace(_venta(2, precio=900_000, firme=True), forma=1)
    salen = comparables_de([en_forma, hundido], _objetivo(), AHORA)
    assert {c.venta.forma for c in salen} == {6, 1}
    assert len({c.peso for c in salen}) == 1


@pytest.mark.parametrize("forma", [-1, 0])
def test_una_forma_que_no_sabemos_se_distingue_de_una_mala(forma: int) -> None:
    """`-1` es «no la sabemos» --toda venta anotada antes de la 0112-- y la
    pantalla pinta una raya. Un 0 no es un nivel de forma del juego, que va de
    1 a 8, así que también se calla: inventar «forma nula» sería peor."""
    venta = replace(_venta(1, precio=900_000, firme=True), forma=forma)
    assert venta.forma < 1


# --------------------------------------------------------------------------
# El contrato con la tabla
# --------------------------------------------------------------------------


def test_los_nombres_nuevos_llegan_a_la_tabla_como_los_lee() -> None:
    """Los cuatro campos nuevos, con el nombre EXACTO que espera la pantalla.

    POR QUÉ ESTO SE PRUEBA. El endpoint pasa el DTO por `_camel`, que es
    genérico: nadie declara en ningún sitio que `precio_pedido` se verá como
    `precioPedido`. Si el camelizador cambiara de regla, o si alguien
    renombrara un campo aquí, la tabla recibiría `undefined` y pintaría una
    raya en silencio --no un error-- en la columna de un dato que sí está.

    Son los nombres que usa `ComparableDeMercado` en
    `frontend/src/services/api/transferencias.ts`.
    """
    from dataclasses import asdict

    from app.api.v1.endpoints.arena import _camel
    from app.application.queries.precio_comparable import FilaDeComparable, RasgoVisible

    fila = FilaDeComparable(
        ht_player_id=472301981,
        nombre="El que se vendió sin que lo viéramos",
        precio=1_241_000,
        puja=0,
        peso=100,
        avalado_por_hattrick=True,
        firme=True,
        cuenta=True,
        viejo=False,
        edad=17,
        dias=24,
        perfil=(
            RasgoVisible("scoring", 18),
            RasgoVisible("passing", 13),
            RasgoVisible("playmaking", 7),
        ),
        semanas=1,
        cierra=AHORA,
        especialidad="",
        tsi=150_000,
        forma=6,
        precio_pedido=2_000_000,
        sin_puja=True,
        pais_codigo="es",
        pais_nombre="España",
    )
    salida = _camel(asdict(fila))
    assert salida["dias"] == 24
    assert salida["forma"] == 6
    assert salida["precioPedido"] == 2_000_000
    assert salida["sinPuja"] is True
    # Y los de siempre siguen donde estaban: esta prueba no vale de nada si el
    # resto del contrato se rompió por el camino.
    assert salida["htPlayerId"] == 472301981
    assert salida["avaladoPorHattrick"] is True
