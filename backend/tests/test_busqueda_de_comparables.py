"""El turno de un jugador, de punta a punta.

Aqui se vigila el GASTO y el orden, que es lo que aporta esta capa: que no se
llame a nadie cuando no hace falta, que se pare en el escalon que completa el
fondo y no antes de terminarlo, y que un anuncio sin puja se guarde --para
poder cazarlo si algun dia se vende-- sin convertirse en un precio.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.application.queries.mercado_comparable import correr_el_turno
from app.domain.engines.mercado_comparable import (
    ORDEN_DE_DESEMPATE,
    Guardado,
    Objetivo,
    Ventana,
    cuenta_para_el_numero,
    nunca_tuvo_puja,
    objetivo_de,
    se_puede_descartar,
    terna,
)

AHORA = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
MI_EQUIPO = 537758
EDAD = 31


def _hab(**niveles: int) -> dict[str, int]:
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 0)
    base.update(niveles)
    return base


SKILLS = _hab(scoring=18, passing=13, playmaking=7)


def _objetivo() -> Objetivo:
    hecho = objetivo_de(777, EDAD, SKILLS)
    assert hecho is not None
    return hecho


def _fila(ident: int, *, puja: int = 4_000_000, **extra: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "ht_player_id": ident,
        "first_name": "Jugador",
        "last_name": str(ident),
        "age_years": EDAD,
        "asking_price": puja,
        "highest_bid": puja,
        "has_bids": puja > 0,
        "deadline": "2026-10-08 20:00:00",
        "tsi": 150_000,
        "specialty": 0,
        "injury_level": -1,
        "seller_team_id": 999_999,
        "seller_league_id": 92,
        "skills": dict(SKILLS),
    }
    fila.update(extra)
    return fila


def _venta(ident: int, *, semanas: float = 0, exacta: bool = True) -> Guardado:
    """Una venta del fondo.

    `exacta=False` la baja un nivel en la SEGUNDA, o sea a un 90%. Hace falta
    desde el 2026-10-07: un comparable que no caduca --el clavado-- no sirve
    para probar la caducidad.

    Era la primaria hasta el 2026-10-10. Dejo de valer cuando se cayo el
    escalon de 85: con la primera desviada un nivel ya no hay comparable, ni
    suyo ni nuestro.

    Y LLEVA LAS SIETE HABILIDADES, como las lleva una venta de verdad desde el
    2026-10-10. Sin ellas no se le puede preguntar por el sello, y desde que la
    escalera nuestra se fue (2026-10-27) una venta que no este clavada se
    quedaria sin peso ninguno.
    """
    skills = dict(SKILLS)
    if not exacta:
        skills["passing"] = skills["passing"] - 1
    tres = terna(skills)
    assert tres is not None
    return Guardado(
        ht_player_id=ident,
        nombre=f"Viejo {ident}",
        precio=1_000_000,
        firme=True,
        puja=1_000_000,
        visto_el=AHORA - timedelta(weeks=semanas),
        edad=EDAD,
        primaria=tres[0],
        secundaria=tres[1],
        terciaria=tres[2],
        habilidades=dict(skills),
    )


class _Mercado:
    """Un mercado de mentira que apunta que se le pidio y en que orden."""

    def __init__(self, *paginas: list[dict[str, Any]]) -> None:
        self.paginas = list(paginas)
        self.pedidas: list[Ventana] = []

    async def __call__(self, ventana: Ventana) -> list[dict[str, Any]]:
        self.pedidas.append(ventana)
        indice = len(self.pedidas) - 1
        return self.paginas[indice] if indice < len(self.paginas) else []


async def _turno(mercado: Any, **kwargs: Any) -> Any:
    return await correr_el_turno(_objetivo(), mercado, mi_equipo=MI_EQUIPO, ahora=AHORA, **kwargs)


async def test_con_el_fondo_vivo_el_turno_solo_gasta_el_escalon_exacto() -> None:
    """La economia principal, con la excepcion que el usuario fijo el
    2026-10-07: un turno con el fondo completo ya no hace NADA salvo el
    escalon exacto, que se recorre siempre.

    Hasta ese dia no gastaba ni una peticion. Ahora gasta una, porque un
    comparable al 100% no caduca y queda grabado, y seguir buscandolo cada
    turno es lo unico que hace que no envejezca de verdad.
    """
    mercado = _Mercado()
    r = await _turno(mercado, fondo=[_venta(i, semanas=1) for i in range(1, 9)])
    assert r.busquedas == 1
    assert len(mercado.pedidas) == 1
    exacta = mercado.pedidas[0]
    assert exacta.peso == 90, "la ventana es la del sello, y el sello vale 90"
    assert r.estimacion.n == 8
    assert r.nuevas == ()
    assert r.por_resolver == ()


async def test_desde_cero_SE_PIDE_UNA_SOLA_VENTANA() -> None:
    """2026-10-26: se acabo la escalera ancha, solo criterios.

    Antes se recorrian los escalones hasta reunir ocho y se paraba al final del
    que cerraba la cuenta --nunca a mitad--, lo que podia costar hasta cinco
    peticiones. Ahora hay una ventana y se pide siempre.
    """
    mercado = _Mercado(
        [_fila(i) for i in range(1, 9)],
        [_fila(90), _fila(91)],  # no deberia pedirse nunca: ya no hay segunda
    )
    r = await _turno(mercado)
    assert r.busquedas == 1
    assert len(r.nuevas) == 8
    assert [v.peso for v in mercado.pedidas] == [90]


async def test_el_escalon_que_cierra_la_cuenta_entra_entero() -> None:
    """Nadie se queda fuera por orden de llegada dentro de un mismo escalon, y
    cuantos mas datos haya mejor se describe el mercado."""
    mercado = _Mercado([_fila(i) for i in range(1, 10)])
    r = await _turno(mercado)
    assert r.busquedas == 1
    assert len(r.nuevas) == 9
    # Las nueve se quedan medidas. Ninguna entra en el numero: son anuncios, y
    # desde el 2026-10-09 solo promedian las ventas cerradas.
    assert len(r.estimacion.comparables) == 9
    assert r.estimacion.n == 0


async def test_si_la_unica_busqueda_no_basta_no_pasa_nada() -> None:
    """Y pasa mucho, que es el precio de haber quitado la escalera.

    Lo que el usuario eligio a cambio es ver el mercado TODOS LOS DIAS: el
    fondo se llena a base de dias, no de anchura. Y el 2026-11-08 lo dijo del
    objetivo de 30: «los 30 se van juntando solos con el tiempo... ambas
    opciones no son definidas por nosotros, sino por la realidad».

    AQUI SE COMPROBABA `agotada`, la bandera de «busque y no llegue a ocho».
    Se fue con el ocho: nadie la leia --ni la API ni la pantalla-- y ya no hay
    umbral con el que compararse.
    """
    mercado = _Mercado([_fila(1)])
    r = await _turno(mercado)
    assert r.busquedas == 1
    assert r.estimacion.media is None, "un anuncio no es un precio"
    assert len(r.nuevas) == 1


async def test_lo_fresco_del_fondo_ahorra_escalones() -> None:
    """El fondo es del equipo: lo que trajo la busqueda de otro jugador vale
    para este si se le parece, y entonces basta con completar lo que falta."""
    mercado = _Mercado([_fila(9)])
    r = await _turno(mercado, fondo=[_venta(i, semanas=1) for i in range(1, 8)])
    assert r.busquedas == 1
    # Siete ventas cerradas del fondo mas el anuncio recien encontrado: ocho
    # medidos. En el NUMERO entran solo las siete cerradas (2026-10-09).
    assert len(r.estimacion.comparables) == 8
    assert r.estimacion.n == 7
    assert len(r.nuevas) == 1


async def test_lo_caducado_SIGUE_DANDO_NUMERO() -> None:
    """Una venta vieja informa mas que ninguna, asi que cuenta igual.

    «Mientras no haya una persona, un jugador que haya entrado dentro de la
    caracterizacion, esa persona puede seguir asi tenga mas de 24 semanas»
    --usuario, 2026-11-08--. Con ocho datos y un tope de treinta no hay a quien
    relevar, asi que las ocho caducadas se quedan y dan numero.
    """
    mercado = _Mercado([_fila(9)])
    # Ocho caducadas de 25 semanas. Desde el 2026-11-08 da igual que sean
    # clavadas o parecidas: todo caduca, y caducar no saca a nadie.
    fondo = [_venta(i, semanas=25, exacta=False) for i in range(1, 9)]
    r = await _turno(mercado, fondo=fondo)
    assert r.busquedas == 1
    assert r.estimacion.n == 8
    assert r.estimacion.media is not None
    assert len(r.nuevas) == 1
    # Marcadas, todas, para que la pantalla lo pueda decir.
    viejas = [c for c in r.estimacion.comparables if c.venta.firme]
    assert all(c.viejo for c in viejas)


async def test_un_anuncio_sin_puja_se_anota_pero_no_vale_como_precio() -> None:
    """Se guarda, y NO cuenta. Son dos cosas distintas, y hasta hoy eran una.

    Del 2026-10-07 al 2026-11-07 un anuncio sin pujas no se anotaba: se medio
    lo que eran --de 25 parecidos a un jugador, 19 sin una sola puja-- y se
    decidio tirarlos, porque entraban con precio CERO y cero es lo que vale
    `HighestBid` sin pujas.

    EL USUARIO ENCONTRO LO QUE ESO COSTABA, por su nombre: «472301981, este
    jugador debio haber entrado al comparador. No lo tomo porque no tuvo puja
    sino hasta el final». Un anuncio que pasa dias a cero y recibe su primera
    puja en la ultima hora no volvia a verse NUNCA: cuando se vendio, para
    nosotros no existia, y el precio de cierre --el unico dato que cuenta para
    la media-- se perdia.

    Asi que ahora se anota, y lo que se defiende aqui es que anotarlo no lo
    convierte en un precio: entra con cero, no ocupa plaza y no da media.
    """
    mercado = _Mercado([_fila(1), _fila(2, puja=0), _fila(3, puja=0)])
    r = await _turno(mercado)
    # LOS TRES SE GUARDAN, que es el cambio.
    assert {v.ht_player_id for v in r.nuevas} == {1, 2, 3}
    # Y LOS TRES VAN A LA COLA DE RESOLUCION, que es para lo que se guardan:
    # el dia que uno de ellos se venda, se le preguntara su precio real.
    assert {p.ht_player_id for p in r.por_resolver} == {1, 2, 3}
    # Los dos de cero entran con precio cero y sin puja. Un precio pedido es lo
    # que una persona decidio pedir, y no se usa de precio jamas.
    ceros = [v for v in r.nuevas if v.ht_player_id in (2, 3)]
    assert [v.precio for v in ceros] == [0, 0]
    assert all(nunca_tuvo_puja(v) for v in ceros)
    assert not any(cuenta_para_el_numero(v) for v in ceros)
    # Una peticion, la unica que hay. Antes se recorria la escalera entera
    # buscando lo que si sirve; desde el 2026-10-26 lo que falta se busca
    # manana, no mas abajo.
    assert r.busquedas == 1
    # Los tres los CONTO el centinela, que mide si el servidor contesta y no si
    # el anuncio sirve: dos sin puja demuestran que hubo respuesta igual que
    # uno con ella.
    assert r.filas_vistas == 3


async def test_un_mercado_entero_sin_pujas_no_da_ningun_numero() -> None:
    """El caso de Kurt Schonhueb y el de Alberto: todo el mercado parecido esta
    en venta y nadie ha pujado por ninguno.

    Lo correcto sigue siendo quedarse SIN CIFRA, no llenarse de ceros. Lo que
    cambio el 2026-11-07 es que los ocho se guardan para poder cazarlos si
    alguno se vende; lo que no cambia, y es lo que esta prueba defiende, es que
    ocho anuncios a cero no producen ni una media.
    """
    mercado = _Mercado([_fila(i, puja=0) for i in range(1, 9)])
    r = await _turno(mercado)
    assert len(r.nuevas) == 8
    assert r.estimacion.media is None
    assert r.estimacion.n == 0
    assert not any(cuenta_para_el_numero(v) for v in r.nuevas)


async def test_el_anuncio_que_nunca_se_vendio_se_descarta() -> None:
    """Y la otra mitad de la decision: «descartarlos si al final no se
    vendieron».

    Sin esto, guardar los anuncios a cero haria crecer el fondo todos los dias
    sin devolver nada: el barrido es diario y la mayoria de los anuncios
    parecidos no tienen puja. Con esto, el que gasto sus dos comprobaciones sin
    que Hattrick publicara traspaso alguno se va.
    """
    muerto = _venta(1, exacta=False)
    muerto = replace(muerto, puja=0, precio=0, firme=False, intentos=2)
    assert se_puede_descartar(muerto) is True
    # CON PUJA TAMBIEN SE DESCARTA desde el 2026-11-08. Aqui se comprobaba lo
    # contrario --conservaba un dato, «alguien ofrecio ese dinero por alguien
    # asi»-- y el usuario lo cambio a «a cualquiera, puja o no»: una fila sin
    # precio no vale nada, y la alternativa era el zombi eterno.
    assert se_puede_descartar(replace(muerto, puja=5_000, precio=5_000)) is True
    # Y una venta firme no se descarta nunca, aunque nunca le vieramos puja:
    # esa es precisamente la que se vino a buscar.
    assert se_puede_descartar(replace(muerto, firme=True, precio=1_200_000)) is False


async def test_todo_lo_que_entra_queda_anotado_para_resolver() -> None:
    """Mientras tanto vale su puja, que se queda corta: Valerio tenia 65
    millones y cerro en 77,7."""
    mercado = _Mercado([_fila(i) for i in range(1, 9)])
    r = await _turno(mercado)
    assert {p.ht_player_id for p in r.por_resolver} == set(range(1, 9))
    assert all(p.plazo == "2026-10-08 20:00:00" for p in r.por_resolver)
    assert all(not v.firme for v in r.nuevas)
    assert r.estimacion.provisionales == 8


async def test_cada_venta_guarda_su_propio_perfil() -> None:
    """Es lo que permite que el fondo sea del equipo: sin su edad y sus
    habilidades, esta venta solo serviria para quien la encontro."""
    # Un ano menos que el objetivo, que sigue dentro de la ventana de edad que
    # pide Hattrick. Antes este caso llevaba la primaria desviada a 17, y desde
    # el 2026-10-27 eso ya no es comparable de nada: Hattrick nunca mueve la
    # primera habilidad y no queda escalera nuestra que lo recoja.
    mercado = _Mercado([_fila(1, age_years=30, skills=_hab(scoring=18, passing=12, playmaking=7))])
    r = await _turno(mercado)
    venta = r.nuevas[0]
    assert venta.edad == 30
    assert venta.primaria.habilidad == "scoring"
    assert venta.primaria.nivel == 18
    assert venta.secundaria.nivel == 12


async def test_tu_propio_jugador_no_entra_en_su_propio_calculo() -> None:
    mercado = _Mercado([_fila(777), _fila(1)])
    r = await _turno(mercado)
    assert 777 not in {v.ht_player_id for v in r.nuevas}


async def test_los_tuyos_en_venta_tampoco() -> None:
    mercado = _Mercado([_fila(1, seller_team_id=MI_EQUIPO), _fila(2)])
    r = await _turno(mercado)
    assert {v.ht_player_id for v in r.nuevas} == {2}


async def test_si_el_mercado_falla_la_excepcion_sube() -> None:
    """Media escalera recorrida daria un fondo peor que el que toca, y darlo
    sin avisar es lo que no debe pasar."""

    async def roto(ventana: Ventana) -> list[dict[str, Any]]:
        raise TimeoutError("el mercado no contesta")

    with pytest.raises(TimeoutError):
        await _turno(roto)
