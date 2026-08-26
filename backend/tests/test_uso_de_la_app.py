"""El resumen de uso: la aritmetica, que es donde se puede mentir sin que se note."""
from datetime import datetime, timedelta

from app.domain.engines.uso_de_la_app import (
    Evento,
    mas_pulsado,
    modulos,
    por_hora,
    sesiones,
    totales,
)

T0 = datetime(2026, 8, 26, 10, 0, 0)


def _p(sesion, modulo, minuto, visible_ms=0, etiqueta=None):
    return Evento(sesion, "page", modulo, etiqueta, T0 + timedelta(minutes=minuto), visible_ms)


def _c(sesion, modulo, minuto, etiqueta):
    return Evento(sesion, "click", modulo, etiqueta, T0 + timedelta(minutes=minuto))


def test_el_tiempo_de_un_modulo_suma_solo_sus_visitas() -> None:
    e = [
        _p("a", "Juveniles", 0, 60_000),
        _p("a", "Juveniles", 5, 30_000),
        _c("a", "Juveniles", 6, "Qué entrenar"),
        _p("a", "Economía", 8, 15_000),
    ]
    j, eco = modulos(e)
    assert j.modulo == "Juveniles"
    assert j.visitas == 2 and j.clics == 1
    assert j.minutos == 1.5
    assert j.media_por_visita_s == 45.0
    assert eco.visitas == 1 and eco.clics == 0


def test_un_clic_no_cuenta_como_visita() -> None:
    """Si contara, "visitas" mediria interaccion y no entradas, y la media de
    permanencia saldria dividida por un numero inventado."""
    u = modulos([_p("a", "Liga", 0, 10_000), _c("a", "Liga", 1, "Ordenar")])[0]
    assert u.visitas == 1
    assert u.media_por_visita_s == 10.0


def test_la_sesion_va_del_primer_al_ultimo_evento() -> None:
    e = [_p("a", "Liga", 0), _c("a", "Liga", 3, "x"), _p("a", "Copa", 7)]
    s = sesiones(e)[0]
    assert s.duracion_s == 7 * 60
    assert s.paginas == 2 and s.clics == 1
    assert s.modulos == {"Liga", "Copa"}


def test_una_sesion_de_un_solo_evento_dura_cero() -> None:
    """Y no un minuto "por si acaso": no se sabe cuanto se quedo, solo que
    paso por ahi. Inventarlo inflaria la duracion media de todos."""
    assert sesiones([_p("a", "Liga", 0)])[0].duracion_s == 0


def test_las_sesiones_no_se_mezclan() -> None:
    e = [_p("a", "Liga", 0), _p("b", "Copa", 1), _c("b", "Copa", 2, "x")]
    assert {s.sesion for s in sesiones(e)} == {"a", "b"}
    assert len(sesiones(e)) == 2


def test_la_duracion_tipica_es_la_MEDIANA() -> None:
    """Una sola pestana olvidada dispara la media y deja de describir a nadie.

    Aqui: tres sesiones de 1, 2 y 100 minutos. La media diria 34 minutos, que
    no se parece a ninguna de las tres.
    """
    e = [
        _p("a", "Liga", 0), _p("a", "Liga", 1),
        _p("b", "Liga", 0), _p("b", "Liga", 2),
        _p("c", "Liga", 0), _p("c", "Liga", 100),
    ]
    t = totales(e)
    assert t.duracion_media_s == 120, "la de en medio, no el promedio (2.040 s)"


def test_los_totales_cuadran() -> None:
    e = [
        _p("a", "Juveniles", 0, 60_000),
        _c("a", "Juveniles", 1, "Traer"),
        _c("a", "Juveniles", 2, "Traer"),
        _p("b", "Liga", 0, 30_000),
    ]
    t = totales(e)
    assert t.sesiones == 2
    assert t.paginas == 2
    assert t.clics == 2
    assert t.minutos == 1.5
    assert t.clics_por_sesion == 1.0


def test_sin_eventos_no_se_divide_por_cero() -> None:
    t = totales([])
    assert t.sesiones == 0 and t.clics_por_sesion == 0.0 and t.duracion_media_s == 0
    assert modulos([]) == [] and sesiones([]) == []


def test_un_tiempo_negativo_no_resta() -> None:
    """El reloj del navegador puede saltar --cambio de hora, suspension-- y
    mandar una duracion imposible. No puede restarle tiempo a un modulo."""
    u = modulos([_p("a", "Liga", 0, -5_000), _p("a", "Liga", 1, 10_000)])[0]
    assert u.visible_ms == 10_000


def test_los_controles_mas_pulsados_dicen_que_se_usa_de_verdad() -> None:
    """Un modulo puede tener muchas visitas y ni un clic: eso es que se mira,
    no que se use."""
    e = [
        _c("a", "Juveniles", 1, "Qué entrenar"),
        _c("b", "Juveniles", 1, "Qué entrenar"),
        _c("a", "Sincronización", 2, "Sincronizar ahora"),
    ]
    assert mas_pulsado(e)[0] == ("Juveniles · Qué entrenar", 2)


def test_las_horas_dicen_cuando_no_molestar() -> None:
    e = [_p("a", "Liga", 0), _p("a", "Liga", 61)]
    assert por_hora(e) == {10: 1, 11: 1}


# ── Un hallazgo del linter, no del comportamiento ────────────────────────────

def test_ninguna_constante_de_version_CHPP_queda_sin_definir() -> None:
    """2026-08-26. `_best_recent_rating` pedia `matchlineup` con
    `MATCHLINEUP_POSITION_CODE_VERSION`, que vive en `rivals.py` y nunca se
    importo en `sync_team.py`. El `except Exception: continue` de dos lineas
    mas abajo se tragaba el NameError, asi que la funcion devolvia `None`
    SIEMPRE y en silencio --y `None` significa "aun no ha jugado"--.

    Lo encontro `ruff` en CI, que llevaba en rojo desde el 22 de agosto sin que
    nadie lo mirara. Esta prueba lo fija sin depender de que ruff se ejecute.
    """
    import app.application.commands.sync_team as st

    crudo = __import__("inspect").getsource(
        st.SyncTeamHandler._best_recent_rating
    )
    # Se miran solo las lineas de CODIGO: el comentario que explica este mismo
    # fallo nombra la constante rota, y la prueba se cazaria a si misma.
    codigo = [l for l in crudo.splitlines() if not l.lstrip().startswith("#")]

    for nombre in ("MATCHLINEUP_ROLE_VERSION", "MATCHLINEUP_POSITION_CODE_VERSION"):
        if any(nombre in linea for linea in codigo):
            assert hasattr(st, nombre), (
                f"{nombre} se usa en _best_recent_rating pero no existe en el "
                "modulo: el NameError se lo traga el except y la funcion "
                "devuelve None para siempre"
            )
