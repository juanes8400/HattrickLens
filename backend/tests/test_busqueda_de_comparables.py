"""El turno de un jugador, de punta a punta.

Aqui se vigila el GASTO y el orden, que es lo que aporta esta capa: que no se
llame a nadie cuando no hace falta, que se pare en el escalon que completa el
fondo y no antes de terminarlo, y que los anuncios sin puja sean el ultimo
recurso y no el primero.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.application.queries.mercado_comparable import correr_el_turno
from app.domain.engines.mercado_comparable import (
    ESCALERA,
    MINIMO_PARA_BAJAR_A_SIN_PUJA,
    OBJETIVO,
    ORDEN_DE_DESEMPATE,
    Guardado,
    Objetivo,
    Ventana,
    objetivo_de,
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


def _venta(ident: int, *, semanas: float = 0) -> Guardado:
    tres = terna(SKILLS)
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


async def test_con_el_fondo_vivo_el_turno_no_gasta_ni_una_llamada() -> None:
    """Es la economia principal: la mayoria de los turnos no tienen que hacer
    nada, y hacer algo costaria cuota de la aplicacion entera."""
    mercado = _Mercado()
    r = await _turno(mercado, fondo=[_venta(i, semanas=1) for i in range(1, 7)])
    assert r.busquedas == 0
    assert mercado.pedidas == []
    assert r.estimacion.suficiente is True
    assert r.nuevas == ()
    assert r.por_resolver == ()


async def test_desde_cero_se_para_en_el_escalon_que_completa_el_fondo() -> None:
    """Dos en el exacto, cuatro en el siguiente: dos llamadas y ni una mas,
    aunque la escalera tenga cinco escalones."""
    mercado = _Mercado(
        [_fila(1), _fila(2)],
        [_fila(3), _fila(4), _fila(5), _fila(6)],
        [_fila(90), _fila(91)],  # este escalon no deberia pedirse nunca
    )
    r = await _turno(mercado)
    assert r.busquedas == 2
    assert len(r.nuevas) == OBJETIVO
    assert r.agotada is False
    assert [v.peso for v in mercado.pedidas] == [100, 90]


async def test_el_escalon_que_cierra_la_cuenta_entra_entero() -> None:
    """Nadie se queda fuera por orden de llegada dentro de un mismo escalon, y
    cuantos mas datos haya mejor se describe el mercado."""
    mercado = _Mercado([_fila(i) for i in range(1, 10)])
    r = await _turno(mercado)
    assert r.busquedas == 1
    assert len(r.nuevas) == 9
    assert r.estimacion.n == 9


async def test_si_la_escalera_no_basta_queda_constancia() -> None:
    mercado = _Mercado([_fila(1)])
    r = await _turno(mercado)
    assert r.busquedas == len(ESCALERA)
    assert r.agotada is True
    assert r.estimacion.suficiente is False
    assert r.estimacion.media is None


async def test_lo_fresco_del_fondo_ahorra_escalones() -> None:
    """El fondo es del equipo: lo que trajo la busqueda de otro jugador vale
    para este si se le parece, y entonces basta con completar lo que falta."""
    mercado = _Mercado([_fila(9)])
    r = await _turno(mercado, fondo=[_venta(i, semanas=1) for i in range(1, 6)])
    assert r.busquedas == 1
    assert r.estimacion.n == OBJETIVO
    assert len(r.nuevas) == 1


async def test_lo_caducado_cuenta_pero_no_detiene_la_busqueda() -> None:
    """Las ventas viejas siguen dando numero, porque una venta vieja informa
    mas que ninguna. Pero su turno se gasta entero buscando con que
    sustituirlas, que es lo que el usuario pidio."""
    mercado = _Mercado([_fila(9)])
    r = await _turno(mercado, fondo=[_venta(i, semanas=9) for i in range(1, 6)])
    assert r.busquedas == len(ESCALERA)
    assert r.estimacion.n == OBJETIVO
    assert len(r.nuevas) == 1


async def test_los_sin_puja_son_el_ultimo_recurso_y_solo_si_son_bastantes() -> None:
    """Cada uno cuesta una resolucion para averiguar si llego a venderse, asi
    que no se gastan por uno suelto."""
    mercado = _Mercado([_fila(1), _fila(2, puja=0), _fila(3, puja=0)])
    r = await _turno(mercado)
    assert {v.ht_player_id for v in r.nuevas} == {1, 2, 3}
    # Y se recorrio la escalera entera antes de bajar a ellos.
    assert r.busquedas == len(ESCALERA)


async def test_un_solo_anuncio_sin_puja_no_merece_la_resolucion() -> None:
    mercado = _Mercado([_fila(1), _fila(2, puja=0)])
    r = await _turno(mercado)
    assert MINIMO_PARA_BAJAR_A_SIN_PUJA == 2
    assert {v.ht_player_id for v in r.nuevas} == {1}


async def test_si_los_de_puja_bastan_no_se_toca_a_los_sin_puja() -> None:
    mercado = _Mercado([_fila(i) for i in range(1, 7)] + [_fila(80, puja=0), _fila(81, puja=0)])
    r = await _turno(mercado)
    assert {v.ht_player_id for v in r.nuevas} == set(range(1, 7))


async def test_todo_lo_que_entra_queda_anotado_para_resolver() -> None:
    """Mientras tanto vale su puja, que se queda corta: Valerio tenia 65
    millones y cerro en 77,7."""
    mercado = _Mercado([_fila(i) for i in range(1, 7)])
    r = await _turno(mercado)
    assert {p.ht_player_id for p in r.por_resolver} == set(range(1, 7))
    assert all(p.plazo == "2026-10-08 20:00:00" for p in r.por_resolver)
    assert all(not v.firme for v in r.nuevas)
    assert r.estimacion.provisionales == OBJETIVO


async def test_cada_venta_guarda_su_propio_perfil() -> None:
    """Es lo que permite que el fondo sea del equipo: sin su edad y sus
    habilidades, esta venta solo serviria para quien la encontro."""
    mercado = _Mercado([_fila(1, age_years=30, skills=_hab(scoring=17, passing=13, playmaking=7))])
    r = await _turno(mercado)
    venta = r.nuevas[0]
    assert venta.edad == 30
    assert venta.primaria.habilidad == "scoring"
    assert venta.primaria.nivel == 17


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
