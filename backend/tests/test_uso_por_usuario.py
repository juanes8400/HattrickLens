"""Quién usa qué, y a qué se vuelve.

2026-09-01, pedido del usuario: «quiero la información mucho más desglosada por
usuario, casi tan precisa como un log». Hasta entonces todo se agregaba a un
número por módulo, y con doce personas registradas eso esconde justo lo que hay
que saber: si una pantalla la usan nueve o la usa una sola muchas veces.

La distinción que gobierna estas pruebas: VOLUMEN y CARIÑO no son lo mismo. Una
pantalla puede acumular horas porque alguien la dejó abierta; otra tener pocas
visitas pero de mucha gente, y repetidas. La segunda es la que hay que cuidar.
"""

from datetime import UTC, datetime, timedelta

from app.domain.engines import uso_de_la_app as uso

T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def _e(
    usuario: int,
    modulo: str,
    tipo: str = "page",
    *,
    dia: int = 0,
    ms: int = 60_000,
    etiqueta: str | None = None,
    sesion: str | None = None,
    nombre: str = "",
) -> uso.Evento:
    return uso.Evento(
        sesion=sesion or f"s{usuario}-{dia}",
        tipo=tipo,
        modulo=modulo,
        etiqueta=etiqueta,
        cuando=T0 + timedelta(days=dia, minutes=len(modulo)),
        visible_ms=ms if tipo == "page" else 0,
        usuario=usuario,
        nombre=nombre or f"manager{usuario}",
    )


def test_cada_persona_sale_en_su_renglon() -> None:
    filas = uso.por_usuario(
        [
            _e(1, "Juveniles"),
            _e(1, "Juveniles", "click", etiqueta="Ojeadores"),
            _e(2, "Economía"),
        ]
    )
    assert [f.usuario for f in filas] == [1, 2]
    assert filas[0].nombre == "manager1"
    assert filas[0].paginas == 1 and filas[0].clics == 1
    assert filas[1].clics == 0


def test_los_dias_activos_cuentan_dias_distintos_no_visitas() -> None:
    """Volver otro día es la señal de que algo sirve. Diez visitas en una tarde
    no dicen lo mismo que una visita cada día durante diez días."""
    de_un_tiron = [_e(1, "Liga", dia=0) for _ in range(10)]
    repartido = [_e(2, "Liga", dia=d) for d in range(10)]
    filas = {f.usuario: f for f in uso.por_usuario(de_un_tiron + repartido)}
    assert filas[1].dias_activos == 1
    assert filas[2].dias_activos == 10
    assert filas[1].paginas == filas[2].paginas  # el volumen es el mismo


def test_el_modulo_favorito_es_donde_pasa_el_tiempo() -> None:
    filas = uso.por_usuario(
        [
            _e(1, "Juveniles", ms=600_000),
            _e(1, "Economía", ms=60_000),
            _e(1, "Economía", ms=60_000),
        ]
    )
    # Economía tiene MÁS visitas, pero Juveniles se lleva el tiempo.
    assert filas[0].modulo_favorito == "Juveniles"


def test_clics_por_pagina_distingue_mirar_de_trabajar() -> None:
    consulta = uso.por_usuario([_e(1, "Liga") for _ in range(4)])[0]
    trabajo = uso.por_usuario(
        [_e(2, "Alineación")] + [_e(2, "Alineación", "click", etiqueta="x") for _ in range(8)]
    )[0]
    assert consulta.clics_por_pagina == 0.0
    assert trabajo.clics_por_pagina == 8.0


def test_la_adopcion_separa_mucha_gente_de_mucho_rato() -> None:
    """El caso que motiva toda la sección.

    «Solitaria» acumula el triple de visitas, pero de UNA persona. «Coral» la
    usan tres, y a eso se vuelve. Ordenar por volumen pondría primero a la que
    le importa a nadie.
    """
    eventos = [_e(1, "Solitaria", dia=0) for _ in range(9)]
    eventos += [_e(u, "Coral", dia=u) for u in (1, 2, 3)]
    filas = {a.modulo: a for a in uso.adopcion(eventos)}

    assert filas["Solitaria"].visitas == 9 and filas["Solitaria"].usuarios == 1
    assert filas["Coral"].visitas == 3 and filas["Coral"].usuarios == 3
    # El orden manda a Coral delante: primero lo que usa más gente.
    assert uso.adopcion(eventos)[0].modulo == "Coral"


def test_el_alcance_se_mide_contra_los_activos() -> None:
    eventos = [_e(u, "Partidos") for u in (1, 2, 3)]
    a = uso.adopcion(eventos)[0]
    assert a.alcance(activos=3) == 100.0
    assert a.alcance(activos=12) == 25.0
    assert a.alcance(activos=0) == 0.0  # sin nadie activo no se divide


def test_visitas_por_usuario_delata_lo_que_se_abre_una_vez() -> None:
    una_vez = [_e(u, "Curiosidad") for u in (1, 2, 3, 4)]
    de_vuelta = [_e(u, "Diaria", dia=d) for u in (1, 2) for d in range(5)]
    filas = {a.modulo: a for a in uso.adopcion(una_vez + de_vuelta)}
    assert filas["Curiosidad"].visitas_por_usuario == 1.0
    assert filas["Diaria"].visitas_por_usuario == 5.0


def test_dentro_de_cada_pantalla_se_ve_lo_suyo() -> None:
    """El ranking global lo copan las pantallas grandes. Esta es la otra
    pregunta: de los que entran AQUÍ, ¿qué tocan?"""
    eventos = [
        _e(1, "Juveniles", "click", etiqueta="Ojeadores"),
        _e(1, "Juveniles", "click", etiqueta="Ojeadores"),
        _e(1, "Juveniles", "click", etiqueta="Promoción"),
        _e(2, "Economía", "click", etiqueta="Proyección"),
    ]
    dentro = uso.dentro_de(eventos)
    assert dentro["Juveniles"] == [("Ojeadores", 2), ("Promoción", 1)]
    assert dentro["Economía"] == [("Proyección", 1)]


def test_lo_que_nadie_abre_tambien_se_dice() -> None:
    """Un ranking por uso deja el cero fuera del final, donde no se ve. Una
    pantalla que nadie abre es una decisión pendiente, no un hueco."""
    eventos = [_e(1, "Juveniles"), _e(1, "Liga")]
    olvidadas = uso.nunca_tocado(eventos, ["Juveniles", "Liga", "Copa", "Estadio"])
    assert olvidadas == ["Copa", "Estadio"]


def test_sin_eventos_nada_revienta() -> None:
    assert uso.por_usuario([]) == []
    assert uso.adopcion([]) == []
    assert uso.dentro_de([]) == {}
    assert uso.nunca_tocado([], ["Copa"]) == ["Copa"]
