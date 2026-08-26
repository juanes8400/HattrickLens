"""La cuenta de cada ojeador: coste, ingresos y saldo.

2026-08-26. Las reglas las dicto el usuario; aqui se fijan para que no se
puedan cambiar sin querer.
"""
from datetime import datetime, timedelta

from app.domain.engines.cuenta_del_ojeador import (
    COSTE_SEMANAL,
    CuentaDeUnOjeador,
    Descubrimiento,
    Ojeador,
    cuenta,
    semanas_cobradas,
    totales,
)

AHORA = datetime(2026, 8, 26, 12, 0)


def _ojeador(dias_contratado: int = 70, se_fue: datetime | None = None, id_: int = 1):
    return Ojeador(
        ht_scout_id=id_,
        nombre=f"Ojeador {id_}",
        contratado=AHORA - timedelta(days=dias_contratado),
        se_fue=se_fue,
    )


def test_se_cobran_semanas_COMPLETAS() -> None:
    """Media semana no se paga. Redondear hacia arriba le cargaria a un
    ojeador recien contratado un coste que todavia no ha tenido."""
    assert semanas_cobradas(_ojeador(dias_contratado=13), AHORA) == 1
    assert semanas_cobradas(_ojeador(dias_contratado=14), AHORA) == 2


def test_un_ojeador_de_tres_dias_cuesta_CERO() -> None:
    """Y es cierto: todavia no ha costado nada."""
    assert semanas_cobradas(_ojeador(dias_contratado=3), AHORA) == 0


def test_al_despedido_se_le_deja_de_cobrar_el_dia_que_desaparecio() -> None:
    """Hattrick no dice cuando se va un ojeador: se anota la ultima vez que se
    le vio y ahi se cierra su coste."""
    se_fue = AHORA - timedelta(days=35)
    o = _ojeador(dias_contratado=70, se_fue=se_fue)
    assert semanas_cobradas(o, AHORA) == 5, "cinco semanas, no diez"


def test_sin_fecha_de_contratacion_no_se_inventa_un_coste() -> None:
    o = Ojeador(ht_scout_id=9, nombre="Sin fecha", contratado=None)
    assert semanas_cobradas(o, AHORA) == 0


def test_el_saldo_es_lo_que_trajo_menos_lo_que_costo() -> None:
    o = _ojeador(dias_contratado=70)          # 10 semanas -> 50.000
    filas = cuenta(
        [o],
        {1: [Descubrimiento("Ireneo", venta_neta=200_000, reventas=30_000,
                            sigue_en_el_club=False)]},
        AHORA,
    )
    f = filas[0]
    assert f.coste == 10 * COSTE_SEMANAL == 50_000
    assert f.ingresos == 230_000
    assert f.saldo == 180_000
    assert f.traidos == 1 and f.vendidos == 1


def test_un_canterano_que_sigue_en_el_club_no_abona_nada() -> None:
    """Todavia no ha dejado dinero: contarlo seria contar una venta que no
    ha ocurrido."""
    filas = cuenta([_ojeador()], {1: [Descubrimiento("Aun aqui")]}, AHORA)
    assert filas[0].ingresos == 0
    assert filas[0].traidos == 1
    assert filas[0].vendidos == 0


def test_un_ojeador_SIN_canteranos_sale_igual_en_la_tabla() -> None:
    """Es la informacion mas util que puede dar: lleva semanas cobrando y no
    ha traido nada. Esconderlo seria esconder justo eso."""
    filas = cuenta([_ojeador(dias_contratado=70)], {}, AHORA)
    assert len(filas) == 1
    assert filas[0].traidos == 0
    assert filas[0].saldo == -50_000


def test_ordena_del_que_mas_deja_al_que_menos() -> None:
    bueno = _ojeador(id_=1, dias_contratado=70)
    malo = _ojeador(id_=2, dias_contratado=70)
    filas = cuenta(
        [malo, bueno],
        {1: [Descubrimiento("X", venta_neta=1_000_000, sigue_en_el_club=False)]},
        AHORA,
    )
    assert [f.ojeador.ht_scout_id for f in filas] == [1, 2]


def test_los_totales_cuadran_con_las_filas() -> None:
    filas = cuenta(
        [_ojeador(id_=1), _ojeador(id_=2)],
        {1: [Descubrimiento("X", venta_neta=100_000, sigue_en_el_club=False)]},
        AHORA,
    )
    t = totales(filas)
    assert t.ojeadores == 2
    assert t.ingresos == 100_000
    assert t.coste == sum(f.coste for f in filas)
    assert t.saldo == t.ingresos - t.coste


def test_sin_ojeadores_no_se_divide_por_cero() -> None:
    assert cuenta([], {}, AHORA) == []
    t = totales([])
    assert (t.coste, t.ingresos, t.saldo, t.ojeadores, t.traidos) == (0, 0, 0, 0, 0)


def test_el_que_sigue_contratado_se_distingue_del_despedido() -> None:
    vivo = CuentaDeUnOjeador(ojeador=_ojeador(id_=1))
    ido = CuentaDeUnOjeador(ojeador=_ojeador(id_=2, se_fue=AHORA))
    assert vivo.sigue_contratado is True
    assert ido.sigue_contratado is False
