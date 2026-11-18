"""Las alertas de cierre (2026-11-18), regla a regla, con los umbrales que dictó
el usuario."""

from datetime import datetime, timedelta

from app.domain.engines import alertas_de_grupo as ag
from app.domain.engines import alertas_de_plantilla as ap

BASE = {
    "keeper": 1,
    "defending": 10,
    "playmaking": 8,
    "winger": 5,
    "passing": 6,
    "scoring": 4,
    "set_pieces": 3,
}


def jugador(
    pid: int = 1,
    *,
    titularidad: str = "titular",
    rentabilidad: str = "estrellas",
    etapa: str = "pico",
    puesto: str = "central_defender",
    pesan: frozenset[str] = frozenset({"defending", "playmaking"}),
    cambia: dict[str, int] | None = None,
    bajadas_totales: int = 0,
    grupos_propios: dict[int, int] | None = None,
) -> ag.JugadorDelSync:
    hoy = dict(BASE) | (cambia or {})
    return ag.JugadorDelSync(
        ht_player_id=pid,
        name=f"J{pid}",
        titularidad=titularidad,
        rentabilidad=rentabilidad,
        etapa=etapa,
        puesto=puesto,
        pesan=pesan,
        hoy=hoy,
        antes=dict(BASE) if cambia else None,
        bajadas_totales=bajadas_totales,
        grupos_propios=grupos_propios or {},
    )


# ── De grupo ───────────────────────────────────────────────────────────────


def test_a1_titular_con_bajada_solo_si_la_habilidad_pesa() -> None:
    assert ag.titular_con_bajada([jugador(cambia={"defending": 9})])
    assert not ag.titular_con_bajada([jugador(cambia={"scoring": 3})])
    assert not ag.titular_con_bajada([jugador(titularidad="reserva", cambia={"defending": 9})])


def test_a2_la_bajada_le_saca_del_once() -> None:
    j = jugador(cambia={"defending": 9})
    assert ag.la_bajada_le_saca_del_once([j], {1})
    assert not ag.la_bajada_le_saca_del_once([jugador()], {1})


def test_a3_suplente_que_supera_a_un_titular_de_su_puesto() -> None:
    titular = jugador(1, cambia=None)
    suplente = ag.JugadorDelSync(
        ht_player_id=2,
        name="J2",
        titularidad="suplencia",
        rentabilidad="gangas",
        etapa="pico",
        puesto="central_defender",
        pesan=frozenset({"defending"}),
        hoy=BASE | {"defending": 11},
        antes=BASE | {"defending": 10},
    )
    out = ag.suplente_que_empuja([titular, suplente])
    assert len(out) == 1 and "J1" in out[0].title


def test_a4_reserva_que_despierta() -> None:
    assert ag.reserva_que_despierta([jugador(titularidad="reserva", cambia={"defending": 11})])


def test_a5_y_a14_estancadas() -> None:
    promesa = ag.Atraso(1, "J1", "suplencia", "promesa", "passing", 9, 6.0)
    titular = ag.Atraso(2, "J2", "titular", "pico", "passing", 12, 8.0)
    assert len(ag.promesa_estancada([promesa, titular])) == 1
    out = ag.entrenamiento_que_no_llega_al_once([promesa, titular])
    assert len(out) == 1 and "J2" in out[0].detail and "J1" not in out[0].detail


def test_a6_promesa_que_sube() -> None:
    assert ag.promesa_que_sube([jugador(etapa="promesa", cambia={"passing": 7})])
    assert not ag.promesa_que_sube([jugador(etapa="pico", cambia={"passing": 7})])


def test_a7_rotacion_que_asoma() -> None:
    assert ag.rotacion_que_asoma([jugador(cambia={"defending": 11})], {1})
    assert not ag.rotacion_que_asoma([jugador(cambia={"defending": 11})], set())


def test_a8_solo_la_primera_bajada_del_veterano() -> None:
    primera = jugador(etapa="veterano", cambia={"passing": 5}, bajadas_totales=1)
    otra = jugador(etapa="veterano", cambia={"passing": 5}, bajadas_totales=3)
    assert ag.primer_aviso_de_declive([primera])
    assert not ag.primer_aviso_de_declive([otra])


def test_a9_declive_acelerado_con_dos_bajadas() -> None:
    dos = jugador(etapa="declive", cambia={"passing": 5, "scoring": 3})
    una = jugador(etapa="declive", cambia={"passing": 5})
    assert ag.declive_acelerado([dos]) and not ag.declive_acelerado([una])


def test_a10_estrella_que_cae() -> None:
    assert ag.estrella_que_cae([jugador(cambia={"playmaking": 7})])
    assert not ag.estrella_que_cae([jugador(rentabilidad="caros", cambia={"playmaking": 7})])


def test_a11_caro_que_baja_otra_vez() -> None:
    otra_vez = jugador(rentabilidad="caros", cambia={"passing": 5}, bajadas_totales=2)
    primera = jugador(rentabilidad="caros", cambia={"passing": 5}, bajadas_totales=1)
    assert ag.caro_que_sigue_bajando([otra_vez]) and not ag.caro_que_sigue_bajando([primera])


def test_a12_ganga_que_sube() -> None:
    assert ag.ganga_que_se_revaloriza([jugador(rentabilidad="gangas", cambia={"winger": 6})])


def test_a13_el_grupo_cae_tres_semanas_con_la_misma_gente() -> None:
    cae = ag.SerieDeGrupo("Titular", "titularidad-titular", "passing", [7, 6.8, 6.5, 6.2], [11] * 4)
    dos = ag.SerieDeGrupo("Titular", "titularidad-titular", "passing", [7, 7.1, 6.5, 6.2], [11] * 4)
    otra_gente = ag.SerieDeGrupo("Titular", "x", "passing", [7, 6.8, 6.5, 6.2], [11, 11, 10, 10])
    assert ag.el_grupo_cae([cae])
    assert not ag.el_grupo_cae([dos])
    assert not ag.el_grupo_cae([otra_gente])


def test_a15_tu_grupo_se_movio() -> None:
    g = ag.GrupoPropio(id=5, nombre="Vender", clasificacion_id=3, clasificacion="Mercado")
    dentro = jugador(cambia={"passing": 7}, grupos_propios={3: 5})
    quieto = jugador(2, grupos_propios={3: 5})
    out = ag.tu_grupo_se_movio([dentro, quieto], [g])
    assert len(out) == 1 and "1 subida(s)" in out[0].title


# ── Generales ──────────────────────────────────────────────────────────────


def test_b1_resistencia_dos_niveles_por_debajo() -> None:
    assert ap.resistencia_baja_para_su_edad([ap.Resistencia(1, "J1", 5, 7)])
    assert not ap.resistencia_baja_para_su_edad([ap.Resistencia(1, "J1", 6, 7)])


def _titular(pid: int, **cambios: object) -> ap.Titular:
    base: dict[str, object] = {
        "ht_player_id": pid,
        "name": f"J{pid}",
        "en_venta": False,
        "experiencia": 6,
        "ultimo_partido": datetime(2026, 11, 15),
    }
    return ap.Titular(**(base | cambios))  # type: ignore[arg-type]


def test_b2_titular_en_venta() -> None:
    assert ap.titular_en_venta([_titular(1, en_venta=True)])
    assert not ap.titular_en_venta([_titular(1)])


def test_b3_venta_con_ganancia_con_la_cuenta_del_simulador() -> None:
    v = ap.Venta(
        1, "J1", precio=1_000_000, gastos=800_000, comision_de_la_casa=0.1, comision_de_reventa=0
    )
    assert ap.precio_de_equilibrio(v) == 888_889
    assert ap.venta_con_ganancia([v], "€")
    barata = ap.Venta(
        1, "J1", precio=850_000, gastos=800_000, comision_de_la_casa=0.1, comision_de_reventa=0
    )
    assert not ap.venta_con_ganancia([barata], "€")


def test_b4_precio_que_sube_un_15() -> None:
    assert ap.precio_que_sube([ap.PrecioSemanal(1, "J1", 100, 115)])
    assert not ap.precio_que_sube([ap.PrecioSemanal(1, "J1", 100, 114)])


def test_b5_comision_a_la_vista_hasta_que_cierra() -> None:
    ahora = datetime(2026, 11, 18, 12)
    abierta = ap.Reventa(482265359, "Domenico Moffa", ahora + timedelta(days=3), 0.025)
    cerrada = ap.Reventa(2, "J2", ahora - timedelta(hours=1), None)
    out = ap.comision_a_la_vista([abierta, cerrada], ahora)
    assert len(out) == 1 and "2.5%" in out[0].detail


def test_b9_titular_tres_niveles_por_debajo_de_la_media() -> None:
    once = [_titular(i, experiencia=8) for i in range(1, 11)] + [_titular(11, experiencia=4)]
    out = ap.titular_sin_experiencia(once)
    assert [i.evidence["ht_player_id"] for i in out] == [11]


def test_b12_juvenil_17_anos_y_112_dias() -> None:
    listo = ap.Juvenil(1, "Y1", 17, 0, 112)
    joven = ap.Juvenil(2, "Y2", 16, 111, 300)
    reciente = ap.Juvenil(3, "Y3", 18, 0, 111)
    out = ap.juvenil_listo_para_subir([listo, joven, reciente])
    assert [i.evidence["ht_youth_player_id"] for i in out] == [1]


def test_b14_titular_que_no_jugo_los_dos_ultimos_oficiales() -> None:
    oficiales = [datetime(2026, 11, 15), datetime(2026, 11, 8), datetime(2026, 11, 1)]
    juega = _titular(1, ultimo_partido=datetime(2026, 11, 15))
    fuera = _titular(2, ultimo_partido=datetime(2026, 11, 1))
    nunca = _titular(3, ultimo_partido=None)
    out = ap.titular_que_no_juega([juega, fuera, nunca], oficiales)
    assert sorted(i.evidence["ht_player_id"] for i in out) == [2, 3]
    assert ap.titular_que_no_juega([fuera], oficiales[:1]) == []


def test_una_misma_bajada_sale_en_una_sola_alerta() -> None:
    """Caso real del usuario: titular, veterano en su primera bajada y estrella."""
    j = jugador(etapa="veterano", cambia={"defending": 9}, bajadas_totales=1)
    sueltas = [
        *ag.titular_con_bajada([j]),
        *ag.primer_aviso_de_declive([j]),
        *ag.estrella_que_cae([j]),
    ]
    assert len(sueltas) == 3
    juntas = ag.juntar_por_jugador(sueltas)
    assert len(juntas) == 1
    assert juntas[0].key == "group.starter_drop.1"
    assert "Primera bajada de veterano, Estrella que cae" in juntas[0].detail


def test_bajadas_y_subidas_no_se_mezclan_ni_entre_jugadores() -> None:
    baja = ag.titular_con_bajada([jugador(1, cambia={"defending": 9})])
    sube = ag.ganga_que_se_revaloriza([jugador(1, rentabilidad="gangas", cambia={"winger": 6})])
    otro = ag.titular_con_bajada([jugador(2, cambia={"defending": 9})])
    assert len(ag.juntar_por_jugador([*baja, *sube, *otro])) == 3
