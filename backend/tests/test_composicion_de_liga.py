"""La comprobación de la composición de la liga.

2026-11-07, pedido del usuario: «crea un mecanismo continuo de verificación
para verificar la composición de la liga».

Lo que importa aquí es que los casos NO se confundan entre sí. Un reemplazo, un
renombrado, una foto a medias y una serie nueva se parecen muchísimo mirando
sólo «quién falta», y cada confusión tiene su propio coste:

· un renombrado tratado como reemplazo trasladaría los partidos de un equipo a
  sí mismo y anunciaría un club nuevo que no existe;
· un reemplazo tratado como renombrado dejaría el calendario apuntando a un id
  muerto, que es exactamente el fallo de etbenianos1 del 2026-09-13;
· una foto a medias tratada como un cambio de liga diría que se fueron cuatro
  equipos cuando lo que pasó es que la llamada se cortó;
· una serie nueva tratada como un cambio anunciaría los ocho equipos como
  novedad cada vez que se asciende o se baja.
"""

from app.domain.engines.composicion_de_liga import (
    PLAZAS_DE_UNA_SERIE,
    Equipo,
    cambios_de,
    sin_repetir,
    verificar,
)

OCHO = [Equipo(ht_team_id=100 + i, nombre=f"Equipo {i}") for i in range(8)]


def test_la_serie_tiene_ocho_plazas() -> None:
    assert PLAZAS_DE_UNA_SERIE == 8


def test_la_misma_composicion_cuadra_y_no_se_dice_nada() -> None:
    """Es el caso normal, y el que NO se enseña: un panel que dice «todo bien»
    en cada sincronización enseña a saltárselo, y el día que traiga algo de
    verdad no se mira."""
    v = verificar(OCHO, OCHO)
    assert v.cuadra is True
    assert v.hay_que_decirlo is False
    assert v.llegaron == 8


def test_un_reemplazo_limpio_se_reconoce_y_se_arregla_solo() -> None:
    """El caso de etbenianos1 y Kivaré: uno se fue, uno llegó con otro id. Es
    el único que el traslado automático de partidos puede resolver sin
    preguntarle nada a nadie."""
    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    llegados = [*OCHO[:-1], nuevo]
    v = verificar(OCHO, llegados)
    assert v.reemplazo_limpio == (OCHO[-1], nuevo)
    assert v.se_arregla_solo is True
    assert v.hay_que_decirlo is True


def test_dos_reemplazos_a_la_vez_no_se_arreglan_solos() -> None:
    """AQUI SE RENDIA EL CODIGO VIEJO, en silencio: `trasladar_equipo_
    reemplazado` devuelve 0 en cuanto no es uno por uno, y nadie se enteraba.

    Ahora se ve: salieron dos, entraron dos, y no hay forma de saber cuál
    ocupa el sitio de cuál sin preguntar. Lo honesto es decirlo y no adivinar.
    """
    a = Equipo(ht_team_id=901, nombre="Uno nuevo")
    b = Equipo(ht_team_id=902, nombre="Otro nuevo")
    v = verificar(OCHO, [*OCHO[:-2], a, b])
    assert len(v.salieron) == 2
    assert len(v.entraron) == 2
    assert v.reemplazo_limpio is None
    assert v.se_arregla_solo is False
    assert v.hay_que_decirlo is True


def test_un_renombrado_no_es_un_reemplazo() -> None:
    """Mismo id, otro nombre: un manager cambia el nombre de su club cuando
    quiere. No entró ni salió nadie, así que no hay partidos que trasladar."""
    renombrado = Equipo(ht_team_id=OCHO[3].ht_team_id, nombre="Ya no me llamo así")
    v = verificar(OCHO, [*OCHO[:3], renombrado, *OCHO[4:]])
    assert v.entraron == ()
    assert v.salieron == ()
    assert len(v.renombrados) == 1
    assert v.renombrados[0].ht_team_id == OCHO[3].ht_team_id
    assert v.renombrados[0].antes == "Equipo 3"
    assert v.renombrados[0].ahora == "Ya no me llamo así"
    # Hay que decirlo --el usuario ve otro nombre en su clasificación-- pero no
    # hay nada que arreglar.
    assert v.hay_que_decirlo is True
    assert v.se_arregla_solo is False


def test_un_nombre_vacio_no_cuenta_como_renombrado() -> None:
    """Vacío es «no lo sabíamos», no un nombre nuevo. Pasa en las filas viejas
    y en una foto que llegó sin nombres; anunciarlo sería inventar un cambio.
    """
    sin_nombre = Equipo(ht_team_id=OCHO[0].ht_team_id, nombre="")
    assert verificar([sin_nombre, *OCHO[1:]], OCHO).renombrados == ()
    assert verificar(OCHO, [sin_nombre, *OCHO[1:]]).renombrados == ()


def test_una_foto_a_medias_no_es_un_cambio_de_liga() -> None:
    """Llegaron siete de ocho. Mirando sólo `salieron` parecería que un equipo
    se fue, y trasladar sus partidos los mandaría al sitio equivocado: el «uno
    que falta» puede ser el que no llegó, no el que se fue."""
    v = verificar(OCHO, OCHO[:7])
    assert v.foto_incompleta is True
    assert v.llegaron == 7
    assert len(v.salieron) == 1
    # Se dice, porque algo no cuadra. Pero NO se arregla solo, aunque parezca
    # un reemplazo de uno: no entró nadie, así que ni eso.
    assert v.hay_que_decirlo is True
    assert v.se_arregla_solo is False


def test_una_foto_a_medias_con_un_equipo_nuevo_tampoco_se_toca() -> None:
    """Siete equipos, y uno de ellos es nuevo.

    Visto de cerca: entró uno y «salieron» dos --el reemplazado y el que no
    llegó-- así que no hay pareja que trasladar. Es justo el caso en el que
    adivinar haría daño, porque el candidato obvio a ocupar el sitio del nuevo
    es uno de los dos y no se puede saber cuál.
    """
    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    v = verificar(OCHO, [*OCHO[:6], nuevo])
    assert v.llegaron == 7
    assert len(v.entraron) == 1
    assert len(v.salieron) == 2
    assert v.reemplazo_limpio is None
    assert v.foto_incompleta is True
    assert v.se_arregla_solo is False


def test_una_serie_nueva_no_es_un_hallazgo() -> None:
    """Primera vez, o un ascenso, o un descenso, o el salto de temporada. Los
    ocho salen como «entraron» y eso no es un cambio: es que no había nada con
    lo que comparar. Anunciarlos como novedad sería ruido en cada temporada."""
    v = verificar([], OCHO)
    assert v.sin_nada_guardado is True
    assert len(v.entraron) == 8
    assert v.salieron == ()
    assert v.hay_que_decirlo is False


def test_una_serie_entera_distinta_si_es_un_hallazgo() -> None:
    """Ocho guardados, ocho llegados, y ninguno coincide. Eso NO es una serie
    nueva: es que la serie guardada y la que llega no son la misma, y mezclar
    sus clasificaciones daría una tabla que no existe."""
    otros = [Equipo(ht_team_id=500 + i, nombre=f"Otro {i}") for i in range(8)]
    v = verificar(OCHO, otros)
    assert v.sin_nada_guardado is False
    assert len(v.entraron) == 8
    assert len(v.salieron) == 8
    assert v.hay_que_decirlo is True
    assert v.se_arregla_solo is False


def test_sin_nada_a_los_dos_lados_no_dice_nada() -> None:
    """Ni guardado ni llegado: no hay liga sincronizada todavía.

    NO SE AVISA, y es importante: mirando sólo `salieron` esto se parecería a
    «se fueron los ocho equipos», que sería anunciar un desastre inexistente la
    primera vez que alguien abre la aplicación.
    """
    v = verificar([], [])
    assert v.llegaron == 0
    assert v.foto_incompleta is False
    assert v.hay_que_decirlo is False


def test_una_liga_que_llega_vacia_tampoco_avisa() -> None:
    """Teníamos ocho y la llamada no trajo ninguno. Eso es la llamada, no la
    liga: los ocho equipos siguen ahí."""
    v = verificar(OCHO, [])
    assert v.llegaron == 0
    assert len(v.salieron) == 8
    assert v.hay_que_decirlo is False
    assert v.se_arregla_solo is False


def test_un_id_cero_se_ignora() -> None:
    """Una fila sin id no es un equipo. Contarla haría que la foto pareciera
    completa con siete equipos de verdad y un hueco con nombre."""
    v = verificar(OCHO, [*OCHO, Equipo(ht_team_id=0, nombre="basura")])
    assert v.llegaron == 8
    assert v.cuadra is True


def test_las_plazas_se_pueden_cambiar() -> None:
    """No se dan por ocho escondidas en el código: una serie con otro tamaño
    --o una comprobación sobre una copa-- tiene que poder decirlo."""
    cuatro = OCHO[:4]
    assert verificar(cuatro, cuatro, plazas=4).cuadra is True
    assert verificar(cuatro, cuatro, plazas=8).foto_incompleta is True


# --------------------------------------------------------------------------
# Las frases que acaban en Cambios
# --------------------------------------------------------------------------


def _frases(guardados, llegados, plazas: int = 8) -> list[str]:
    return [c.summary for c in cambios_de(verificar(guardados, llegados, plazas))]


def test_lo_que_cuadra_no_deja_ni_una_fila() -> None:
    assert _frases(OCHO, OCHO) == []


def test_la_serie_nueva_no_deja_ni_una_fila() -> None:
    """Ocho líneas de «entró en la liga» cada vez que se asciende o se baja
    serían ruido, y no un hallazgo."""
    assert _frases([], OCHO) == []


def test_un_reemplazo_se_dice_en_una_sola_frase() -> None:
    """Y no en dos --«salió X», «entró Y»--: lo que el usuario necesita saber es
    que uno ocupa el sitio del otro, que es justo lo que se perdía cuando había
    que leer dos líneas separadas."""
    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    frases = _frases(OCHO, [*OCHO[:-1], nuevo])
    assert frases == ["Equipo 7 fue reemplazado por Kivaré en la liga"]


def test_un_renombrado_se_dice_con_los_dos_nombres() -> None:
    renombrado = Equipo(ht_team_id=OCHO[2].ht_team_id, nombre="Kivaré")
    frases = _frases(OCHO, [*OCHO[:2], renombrado, *OCHO[3:]])
    assert frases == ["Equipo 2 ahora se llama Kivaré"]


def test_dos_entradas_y_dos_salidas_se_enumeran() -> None:
    """Con pocos equipos movidos se dice QUIÉN: es lo que hace falta para ir a
    mirar. Y no hay reemplazo limpio, así que no se insinúa ninguna pareja."""
    a = Equipo(ht_team_id=901, nombre="Uno")
    b = Equipo(ht_team_id=902, nombre="Otro")
    frases = _frases(OCHO, [*OCHO[:-2], a, b])
    assert "Uno entró en la liga" in frases
    assert "Otro entró en la liga" in frases
    assert "Equipo 6 ya no está en la liga" in frases
    assert "Equipo 7 ya no está en la liga" in frases
    assert len(frases) == 4


def test_media_liga_cambiada_se_resume() -> None:
    """Dieciséis líneas no informan más que una: lo que ha pasado es que la
    serie guardada y la que llega no son la misma."""
    otros = [Equipo(ht_team_id=500 + i, nombre=f"Otro {i}") for i in range(8)]
    frases = _frases(OCHO, otros)
    assert frases == ["La liga cambió de equipos: entraron 8 y se fueron 8"]


def test_una_foto_a_medias_lo_dice_y_no_dice_nada_mas() -> None:
    """MIENTRAS LA FOTO NO ESTÉ COMPLETA, todo lo demás que se lea de ella puede
    ser un artefacto de la llamada y no un cambio. Decir «se fue el Equipo 7»
    mandaría al usuario a buscar a un equipo que sigue ahí."""
    frases = _frases(OCHO, OCHO[:7])
    assert frases == [
        "La clasificación llegó con 7 equipos de 8: no se ha dado por cambiada la liga"
    ]


def test_un_reemplazo_y_un_renombrado_a_la_vez_se_dicen_los_dos() -> None:
    """Son cosas distintas y pueden pasar la misma semana: uno entró y a otro le
    cambiaron el nombre. Ninguna tapa a la otra."""
    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    renombrado = Equipo(ht_team_id=OCHO[0].ht_team_id, nombre="Ya no soy ése")
    frases = _frases(OCHO, [renombrado, *OCHO[1:-1], nuevo])
    assert "Equipo 7 fue reemplazado por Kivaré en la liga" in frases
    assert "Equipo 0 ahora se llama Ya no soy ése" in frases
    assert len(frases) == 2


def test_las_frases_llevan_su_categoria_y_su_etiqueta() -> None:
    """`category="liga"` las pone con el resto de lo de la liga. Y NO entran en
    las categorías que hacen que una sincronización cuente como «tuvo cambios»:
    eso es para lo que le pasó a TU club, y esto le pasó a la serie."""
    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    cambios = cambios_de(verificar(OCHO, [*OCHO[:-1], nuevo]))
    assert [c.category for c in cambios] == ["liga"]
    assert [c.metric for c in cambios] == ["composicion"]
    assert [c.kind for c in cambios] == ["event"]


# --------------------------------------------------------------------------
# No decir dos veces lo mismo
# --------------------------------------------------------------------------


def test_un_hallazgo_ya_dicho_no_se_repite() -> None:
    """LA FOTO GUARDADA NO SE ACTUALIZA HASTA LA JORNADA SIGUIENTE, y una
    jornada se guarda una sola vez. Si el reemplazo ocurre después de ese
    guardado --que es lo normal: un equipo se abandona cuando se abandona-- el
    mismo aviso saldría en cada sincronización durante días.

    `trasladar_equipo_reemplazado` no tiene este problema porque se cura solo:
    cambia los partidos y a la segunda no encuentra nada. Esto sólo mira, así
    que la memoria es lo que ya se dijo.
    """
    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    hallazgos = cambios_de(verificar(OCHO, [*OCHO[:-1], nuevo]))
    assert len(hallazgos) == 1
    assert sin_repetir(hallazgos, []) == hallazgos
    assert sin_repetir(hallazgos, [hallazgos[0].summary]) == ()


def test_otro_reemplazo_distinto_si_se_dice() -> None:
    """Callar el mismo no puede callar el siguiente: la semana que viene puede
    desaparecer otro equipo, y ése es un hallazgo nuevo."""
    primero = Equipo(ht_team_id=999, nombre="Kivaré")
    segundo = Equipo(ht_team_id=998, nombre="Otro cualquiera")
    uno = cambios_de(verificar(OCHO, [*OCHO[:-1], primero]))
    dos = cambios_de(verificar(OCHO, [*OCHO[:-1], segundo]))
    assert sin_repetir(dos, [uno[0].summary]) == dos


def test_un_renombrado_de_vuelta_se_dice_otra_vez() -> None:
    """«Ahora se llama X» después de «ahora se llama Y» es otra frase, y es lo
    correcto: el club volvió a cambiarse el nombre."""
    ida = Equipo(ht_team_id=OCHO[0].ht_team_id, nombre="Kivaré")
    vuelta = Equipo(ht_team_id=OCHO[0].ht_team_id, nombre="Equipo 0")
    primera = cambios_de(verificar(OCHO, [ida, *OCHO[1:]]))
    segunda = cambios_de(verificar([ida, *OCHO[1:]], [vuelta, *OCHO[1:]]))
    assert sin_repetir(segunda, [primera[0].summary]) == segunda


# --------------------------------------------------------------------------
# Las frases llegan traducidas
# --------------------------------------------------------------------------


def test_todas_las_frases_estan_en_los_cuatro_idiomas() -> None:
    """Una frase del servidor sin entrada en `app/i18n` sale en español a un
    manager alemán, y no avisa nadie.

    POR QUE ESTO SE PRUEBA ASI Y NO MIRANDO EL JSON. Las frases llevan huecos
    --«{} fue reemplazado por {} en la liga»-- y el traductor las reconoce por
    un patrón compilado, no por igualdad: una entrada con un hueco de más, una
    coma donde no toca o un acento distinto está en el fichero y NO casa. Lo
    único que demuestra que funciona es pasarle la frase real, ya con los
    nombres dentro, y comprobar que sale otra.
    """
    import json
    from pathlib import Path

    from app.i18n.traductor import Traductor

    nuevo = Equipo(ht_team_id=999, nombre="Kivaré")
    renombrado = Equipo(ht_team_id=OCHO[0].ht_team_id, nombre="Ya no soy ése")
    otros = [Equipo(ht_team_id=500 + i, nombre=f"Otro {i}") for i in range(8)]
    a, b = Equipo(ht_team_id=901, nombre="Uno"), Equipo(ht_team_id=902, nombre="Otro")

    frases = {
        c.summary
        for veredicto in (
            # Un reemplazo limpio.
            verificar(OCHO, [*OCHO[:-1], nuevo]),
            # Un renombrado.
            verificar(OCHO, [renombrado, *OCHO[1:]]),
            # Dos y dos, que se enumeran.
            verificar(OCHO, [*OCHO[:-2], a, b]),
            # Media liga, que se resume.
            verificar(OCHO, otros),
            # Una foto a medias.
            verificar(OCHO, OCHO[:7]),
        )
        for c in cambios_de(veredicto)
    }
    # Ocho frases y seis moldes: el caso de «dos y dos» da cuatro frases --un
    # «entró» y un «ya no está» por equipo-- que son dos moldes repetidos con
    # nombres distintos. Lo que importa es que los SEIS moldes que existen
    # estén todos ejercitados, y lo están.
    assert len(frases) == 8
    moldes = {
        "fue reemplazado por",
        "ahora se llama",
        "entró en la liga",
        "ya no está en la liga",
        "cambió de equipos",
        "no se ha dado por cambiada",
    }
    for molde in moldes:
        assert any(molde in f for f in frases), molde

    raiz = Path(__file__).resolve().parents[1] / "app" / "i18n"
    sin_traducir: list[str] = []
    for idioma in ("en", "de", "it", "pl"):
        tr = Traductor(json.loads((raiz / f"{idioma}.json").read_text(encoding="utf-8")))
        for frase in frases:
            if tr.texto(frase) == frase:
                sin_traducir.append(f"{idioma}: {frase}")
    assert sin_traducir == []
