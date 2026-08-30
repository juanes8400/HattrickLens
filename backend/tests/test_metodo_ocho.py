"""El método 8: los tres caminos, y por qué cada uno.

Firmado el 2026-08-30. Los casos vienen de la simulación que se corrió con el
usuario antes de implementarlo, así que cada prueba es un escenario que él
miró y aprobó.
"""

from app.domain.engines import youth_skill_score as yss
from app.domain.engines.metodo_ocho import (
    DESCUBRIR,
    DOBLAR,
    INDIVIDUAL,
    SEGUNDA,
    Habilidad,
    decidir,
)

PESOS = {b: w / yss.SQUAD_NORMALISER for b, w in yss.weights_for().items()}
BONUS = yss.trainable_weight_for() / yss.SQUAD_NORMALISER


def hab(label: str, bonus_n: float = 0.0, **cubos: int) -> Habilidad:
    return Habilidad(
        skill=label.lower(),
        label=label,
        cubos=cubos,
        pesos=PESOS,
        bonus=bonus_n * BONUS,
    )


def ruido(label: str, bonus_n: float = 0.0, **extra: int) -> Habilidad:
    """Una habilidad a oscuras, como las seis que tenía el usuario."""
    cubos = {"desconocido_pronto": 13, "desconocido_tarde": 4}
    cubos.update(extra)
    return hab(label, bonus_n, **cubos)


def otras() -> list[Habilidad]:
    return [
        ruido("Balón parado", 11),
        ruido("Pases", 8, desconocido_pronto=10, aceptable_tarde=1),
        ruido("Jugadas", 5),
        ruido("Defensa", 5),
        ruido("Portería", 1),
        ruido("Anotación", 3, desconocido_pronto=11),
    ]


def test_hoy_un_bueno_joven_no_dobla():
    """El caso real del usuario. Su Lateral vale 1,95 pero es UN chico: al
    quitárselo se cae del primer puesto, así que doblar concentraría en él."""
    v = decidir(
        [ruido("Lateral", 4, bueno_pronto=1, desconocido_pronto=11, desconocido_tarde=3)] + otras()
    )
    assert v is not None
    assert v.camino == DESCUBRIR
    assert (v.principal, v.secundaria) == ("lateral", INDIVIDUAL)
    assert not v.robusta


def test_dos_buenos_ya_es_un_grupo_y_dobla():
    v = decidir(
        [ruido("Lateral", 4, bueno_pronto=2, desconocido_pronto=10, desconocido_tarde=3)] + otras()
    )
    assert v is not None
    assert v.camino == DOBLAR
    assert v.principal == v.secundaria == "lateral"
    assert v.robusta


def test_un_excelente_solitario_no_dobla():
    """La prueba de que la robustez hace su trabajo.

    Un excelente da 5,33 de puntaje --casi el triple de lo normal-- y aun así
    NO se dobla: cualquier regla basada en «puntaje alto» habría concentrado
    dos entrenamientos en un solo chico.
    """
    v = decidir(
        [ruido("Lateral", 4, excelente=1, desconocido_pronto=11, desconocido_tarde=3)] + otras()
    )
    assert v is not None
    assert v.puntaje_principal > 5.0
    assert v.camino == DESCUBRIR
    assert not v.robusta


def test_doblar_tiene_prioridad_sobre_la_segunda():
    """Aunque haya una segunda con respaldo de verdad."""
    resto = otras()
    resto[0] = ruido("Balón parado", 11, bueno_tarde=2, desconocido_pronto=11)
    v = decidir(
        [ruido("Lateral", 4, bueno_pronto=2, desconocido_pronto=10, desconocido_tarde=3)] + resto
    )
    assert v is not None
    assert v.camino == DOBLAR


def test_la_segunda_entra_si_tiene_respaldo_y_la_primera_no_es_grupo():
    resto = otras()
    resto[0] = ruido("Balón parado", 11, bueno_tarde=2, desconocido_pronto=11)
    v = decidir(
        [ruido("Lateral", 4, excelente=1, desconocido_pronto=11, desconocido_tarde=3)] + resto
    )
    assert v is not None
    assert v.camino == SEGUNDA
    assert (v.principal, v.secundaria) == ("lateral", "balón parado")


def test_academia_recien_abierta_descubre_por_partida_doble():
    v = decidir([ruido("Lateral", 4)] + otras())
    assert v is not None
    assert v.principal == v.secundaria == INDIVIDUAL


def test_el_suelo_para_a_un_aceptable_a_secas():
    """Peldaño 5 no basta.

    Su no-respaldo se queda en el 82 % --no llega al 90 %-- así que el
    descarte NO la mata. Sin la regla de aptitud se recomendaría entrenar por
    un chico mediano.
    """
    lateral = ruido("Lateral", 4, aceptable_tarde=1, desconocido_pronto=12, desconocido_tarde=3)
    assert lateral.no_respaldo < 0.90  # el descarte no la para
    assert not lateral.apta  # el suelo sí
    v = decidir([lateral] + otras())
    assert v is not None
    assert v.principal == INDIVIDUAL


def test_un_bueno_tarde_si_es_apto():
    """El suelo es «peldaño 4 o mejor», no el cubo exacto: un «bueno» está por
    encima de un «aceptable joven» y sería absurdo que lo descalificara."""
    assert hab("X", bueno_tarde=1).apta
    assert hab("X", aceptable_pronto=1).apta
    assert not hab("X", aceptable_tarde=1).apta
    assert not hab("X", desconocido_pronto=9).apta


def test_quitar_el_mejor_descuenta_uno_solo():
    h = hab("X", bueno_pronto=3)
    assert h.puntaje(h.mejor_peldano) == h.puntaje() - PESOS["bueno_pronto"]


def test_los_que_toparon_no_son_respaldo():
    """No es que no se sepa: es que se sabe que no sube."""
    h = hab("X", al_tope=5, desconocido_pronto=1)
    assert h.no_respaldo == 1.0


def test_sin_habilidades_no_hay_veredicto():
    assert decidir([]) is None


def test_una_sola_habilidad_es_robusta_por_definicion():
    """No hay quien la adelante."""
    v = decidir([hab("Lateral", bueno_pronto=2)])
    assert v is not None
    assert v.robusta
    assert v.camino == DOBLAR


def test_el_motivo_explica_el_camino():
    v = decidir(
        [ruido("Lateral", 4, bueno_pronto=2, desconocido_pronto=10, desconocido_tarde=3)] + otras()
    )
    assert v is not None
    assert "grupo" in v.motivo
    assert "1.95" not in v.motivo  # habla del caso doblado, no del de hoy
