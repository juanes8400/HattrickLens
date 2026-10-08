"""De la puja al precio de verdad, y el disparador semanal.

Lo que se vigila aqui es lo que convierte una promesa en un hecho. Una venta
entra en el fondo con la PUJA de precio, que se queda corta: el 2026-10-05
Valerio Cataldi tenia 65.000.000 de puja y cerro en 77.720.000, un 16% mas. Si
la resolucion falla en silencio, el numero se queda bajo para siempre y nadie
se entera.

Y el disparador: un paso semanal que corra de mas gasta cuota de la aplicacion
entera, y uno que corra de menos deja los precios viejos.
"""

from datetime import UTC, datetime, timedelta

from app.application.commands.mercado_comparable import (
    a_guardado,
    aplicar_resolucion,
    del_turno,
    numero_de_turno,
    toca_el_paso,
)
from app.domain.engines.mercado_comparable import (
    GRUPOS,
    MARGEN_TRAS_EL_PLAZO,
    REINTENTOS_DE_RESOLUCION,
    Traspaso,
    precio_cerrado,
    se_puede_resolver,
)
from app.domain.value_objects.ht_time import ht_to_utc
from app.infrastructure.db import models as m

#: La proxima actualizacion economica de la liga del usuario.
ECONOMICA = datetime(2026, 10, 9, 21, 25, tzinfo=UTC)
#: El disparador: esa fecha menos 24 horas.
DISPARADOR = datetime(2026, 10, 8, 21, 25, tzinfo=UTC)

#: El plazo tal como lo manda Hattrick, en hora sueca, y ya convertido. Las
#: dos puntas de la comparacion pasan por la misma conversion: la del anuncio
#: al guardarlo y la del historial al resolverlo. Escribirlo asi en la prueba
#: evita darlas por iguales cuando no lo son.
PLAZO_HT = "2026-10-05 21:37:00"
PLAZO = ht_to_utc(PLAZO_HT)
assert PLAZO is not None


def _fila(**extra) -> m.MarketSale:
    fila = m.MarketSale(
        team_id=1,
        ht_player_id=465780831,
        name="Valerio Cataldi",
        price=65_000_000,
        bid_price=65_000_000,
        is_final=False,
        deadline=PLAZO,
        seen_at=PLAZO - timedelta(days=1),
        resolve_attempts=0,
        # Explicito porque los defaults de SQLAlchemy se aplican al INSERTAR,
        # no al construir: sin esto el atributo vale None y no 0.
        ht_transfer_id=0,
        age_years=32,
        primary_skill="scoring",
        primary_level=18,
        secondary_skill="playmaking",
        secondary_level=13,
        tertiary_skill="passing",
        tertiary_level=13,
        specialty=0,
    )
    for clave, valor in extra.items():
        setattr(fila, clave, valor)
    return fila


def _historial(*traspasos: tuple[str, int]) -> dict:
    """El historial tal como lo manda `transfersplayer`, CON su TransferID.

    El id es lo que distingue dos traspasos seguidos, y es el unico sitio
    donde Hattrick lo publica: el fichero del mercado no lo trae.
    """
    return {
        "ht_player_id": 465780831,
        "player_name": "Valerio Cataldi",
        "transfers": [
            {"ht_transfer_id": 9_000_001 + i, "deadline": cuando, "price": precio}
            for i, (cuando, precio) in enumerate(traspasos)
        ],
    }


# --------------------------------------------------------------------------
# Cuando se puede preguntar
# --------------------------------------------------------------------------


def test_no_se_pregunta_antes_de_que_cierre_la_subasta() -> None:
    """Preguntar pronto gasta una llamada para no encontrar nada."""
    assert se_puede_resolver(PLAZO, PLAZO - timedelta(hours=1)) is False
    assert se_puede_resolver(PLAZO, PLAZO) is False


def test_se_pregunta_pasado_el_margen_que_tarda_hattrick_en_anotarla() -> None:
    assert timedelta(hours=2) == MARGEN_TRAS_EL_PLAZO
    assert se_puede_resolver(PLAZO, PLAZO + MARGEN_TRAS_EL_PLAZO) is True
    assert se_puede_resolver(PLAZO, PLAZO + timedelta(days=3)) is True


def test_sin_plazo_no_se_pregunta() -> None:
    """A ciegas se gastaria una llamada por cada intento."""
    assert se_puede_resolver(None, PLAZO + timedelta(days=9)) is False


# --------------------------------------------------------------------------
# Encontrar la venta correcta en el historial
# --------------------------------------------------------------------------


def test_se_coge_el_traspaso_de_NUESTRO_plazo_y_no_el_mas_reciente() -> None:
    """El historial trae TODOS los traspasos del jugador. Si volvio a cambiar
    de club despues, el mas reciente es otro traspaso y otro precio."""
    cerrado = precio_cerrado(
        [
            Traspaso(301, PLAZO + timedelta(days=40), 90_000_000),
            Traspaso(302, PLAZO, 77_720_000),
            Traspaso(303, PLAZO - timedelta(days=1500), 70_369_800),
        ],
        PLAZO,
    )
    assert cerrado is not None
    assert cerrado.precio == 77_720_000
    assert cerrado.ht_transfer_id == 302


def test_un_desfase_de_minutos_sigue_siendo_el_mismo_traspaso() -> None:
    cerrado = precio_cerrado([Traspaso(302, PLAZO + timedelta(minutes=3), 77_720_000)], PLAZO)
    assert cerrado is not None and cerrado.precio == 77_720_000


def test_si_ninguno_encaja_no_se_inventa_un_precio() -> None:
    assert precio_cerrado([Traspaso(9, PLAZO + timedelta(days=9), 90_000_000)], PLAZO) is None
    assert precio_cerrado([], PLAZO) is None


def test_con_dos_dentro_de_la_tolerancia_gana_el_mas_cercano() -> None:
    """Dos traspasos seguidos pueden caer los dos en la ventana de cinco
    minutos. Antes se cogia el primero que apareciera, o sea el que Hattrick
    mandara antes; ahora gana el que de verdad cierra en nuestro plazo.

    El caso real medido tenia trece segundos de desfase, asi que el margen
    para equivocarse existe de sobra.
    """
    cerrado = precio_cerrado(
        [
            Traspaso(401, PLAZO + timedelta(minutes=4), 50_000_000),
            Traspaso(402, PLAZO + timedelta(seconds=13), 77_720_000),
        ],
        PLAZO,
    )
    assert cerrado is not None
    assert cerrado.ht_transfer_id == 402
    assert cerrado.precio == 77_720_000


def test_al_resolver_la_venta_se_queda_con_el_id_del_traspaso() -> None:
    """Desde ahi deja de identificarse por una marca de tiempo."""
    fila = _fila()
    resultado = aplicar_resolucion(fila, _historial((PLAZO_HT, 77_720_000)))
    assert resultado.ht_transfer_id > 0
    assert fila.ht_transfer_id == resultado.ht_transfer_id


def test_mientras_sea_puja_no_hay_id_que_guardar() -> None:
    """El fichero del mercado no publica TransferID: mientras la subasta
    vive, la transferencia no ha ocurrido y no tiene identificador."""
    fila = _fila()
    resultado = aplicar_resolucion(fila, _historial())
    assert resultado.ht_transfer_id == 0
    assert fila.ht_transfer_id == 0


# --------------------------------------------------------------------------
# Aplicar la resolucion a la fila
# --------------------------------------------------------------------------


def test_la_puja_se_cambia_por_el_precio_de_verdad() -> None:
    """El caso real de Valerio, de punta a punta."""
    fila = _fila()
    resultado = aplicar_resolucion(fila, _historial((PLAZO_HT, 77_720_000)))
    assert resultado.precio == 77_720_000
    assert fila.price == 77_720_000
    assert fila.is_final is True
    assert resultado.abandonada is False


def test_el_precio_real_puede_ser_muy_distinto_de_la_puja() -> None:
    """Y por eso hay que resolver: la puja de Valerio se quedo un 16% corta."""
    fila = _fila()
    aplicar_resolucion(fila, _historial((PLAZO_HT, 77_720_000)))
    assert fila.price > 65_000_000


def test_si_no_aparece_se_anota_el_intento_y_se_reintenta() -> None:
    """Con una puja encima la venta esta garantizada, asi que no encontrarla
    casi siempre es que Hattrick aun no la habia registrado."""
    fila = _fila()
    resultado = aplicar_resolucion(fila, _historial())
    assert resultado.precio is None
    assert fila.is_final is False
    assert fila.price == 65_000_000
    assert fila.resolve_attempts == 1
    assert resultado.abandonada is False


def test_agotados_los_reintentos_se_deja_con_su_puja() -> None:
    """Insistir mas seria gastar llamadas en balde."""
    fila = _fila(resolve_attempts=REINTENTOS_DE_RESOLUCION)
    resultado = aplicar_resolucion(fila, _historial())
    assert resultado.abandonada is True
    assert fila.is_final is False
    assert fila.price == 65_000_000


def test_un_historial_con_fechas_rotas_no_revienta() -> None:
    fila = _fila()
    resultado = aplicar_resolucion(
        fila, {"transfers": [{"deadline": "manana", "price": 1}, {"deadline": "", "price": 2}]}
    )
    assert resultado.precio is None
    assert fila.is_final is False


# --------------------------------------------------------------------------
# El disparador semanal
# --------------------------------------------------------------------------


def _equipo(sello: datetime | None) -> m.Team:
    equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
    equipo.market_run_at = sello
    return equipo


def test_la_primera_vez_siempre_toca() -> None:
    assert toca_el_paso(_equipo(None), ECONOMICA, DISPARADOR + timedelta(hours=1)) is True


def test_antes_del_disparador_no_toca_aunque_nunca_se_haya_corrido() -> None:
    """La frontera de esa semana es la anterior, y el sello es mas nuevo."""
    equipo = _equipo(DISPARADOR - timedelta(days=5))
    assert toca_el_paso(equipo, ECONOMICA, DISPARADOR - timedelta(hours=1)) is False


def test_una_vez_corrido_no_se_repite_hasta_el_siguiente_disparador() -> None:
    equipo = _equipo(DISPARADOR + timedelta(minutes=5))
    assert toca_el_paso(equipo, ECONOMICA, DISPARADOR + timedelta(days=3)) is False
    assert toca_el_paso(equipo, ECONOMICA, DISPARADOR + timedelta(days=8)) is True


def test_sin_fecha_economica_no_se_corre() -> None:
    """Es la unica fuente del disparador, y Hattrick la da por pais."""
    assert toca_el_paso(_equipo(None), None, DISPARADOR) is False


def test_el_turno_rota_de_cero_a_cuatro() -> None:
    vistos = set()
    for semanas in range(GRUPOS):
        momento = DISPARADOR + timedelta(weeks=semanas, hours=1)
        vistos.add(numero_de_turno(ECONOMICA + timedelta(weeks=semanas), momento))
    assert vistos == set(range(GRUPOS))


def test_cada_semana_le_toca_a_un_solo_grupo() -> None:
    plantilla = list(range(100, 125))
    tocan = del_turno(plantilla, ECONOMICA, DISPARADOR + timedelta(hours=1))
    assert tocan, "alguien tiene que tocar"
    assert len({p % GRUPOS for p in tocan}) == 1
    # Y es una quinta parte larga de la plantilla.
    assert len(tocan) == sum(1 for p in plantilla if p % GRUPOS == tocan[0] % GRUPOS)


def test_sin_fecha_economica_no_le_toca_a_nadie() -> None:
    assert del_turno([1, 2, 3], None, DISPARADOR) == []
    assert numero_de_turno(None, DISPARADOR) is None


# --------------------------------------------------------------------------
# La fila como la ve el motor
# --------------------------------------------------------------------------


def test_la_fila_guarda_el_perfil_para_poder_volver_a_medirla() -> None:
    """Es lo que hace que el fondo sea del equipo: sin su edad y sus tres
    habilidades, esta venta solo serviria para quien la encontro."""
    venta = a_guardado(_fila())
    assert venta.edad == 32
    assert (venta.primaria.habilidad, venta.primaria.nivel) == ("scoring", 18)
    assert (venta.secundaria.habilidad, venta.secundaria.nivel) == ("playmaking", 13)
    assert (venta.terciaria.habilidad, venta.terciaria.nivel) == ("passing", 13)
    assert venta.firme is False
    assert venta.precio == 65_000_000


def test_la_puja_sobrevive_a_la_resolucion() -> None:
    """`price` pasa a ser el precio de cierre, pero la puja con la que entro
    se queda: la diferencia entre las dos es lo que la pantalla ensena, y lo
    que dice cuanto se queda corta una puja (Valerio +16%, Bernacki +2%)."""
    fila = _fila()
    aplicar_resolucion(fila, _historial((PLAZO_HT, 77_720_000)))
    assert fila.price == 77_720_000
    assert fila.bid_price == 65_000_000
