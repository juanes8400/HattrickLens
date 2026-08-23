"""A quien darle los minutos de la habilidad que se esta entrenando.

Es una decision DISTINTA de "que habilidad entreno": el puntaje elige la
habilidad, y esta cola elige a quien se le dan los puestos que reciben ese
entrenamiento. Nueve peldaños, pedidos asi el 2026-08-23.

Antes la lista se ordenaba solo por nota, de mayor a menor, con los
desconocidos al final: ignoraba el plazo, que es lo que decide de verdad.
"""
from app.domain.engines.youth_skill_score import (
    YouthCandidate,
    YouthSkillReading,
    score_skills,
    training_priority,
)


def test_los_nueve_peldaños_en_orden() -> None:
    orden = [
        ("excelente", training_priority(8, leaves_soon=False)),
        ("bueno pronto", training_priority(7, leaves_soon=True)),
        ("bueno tarde", training_priority(7, leaves_soon=False)),
        ("aceptable pronto", training_priority(6, leaves_soon=True)),
        ("aceptable tarde", training_priority(6, leaves_soon=False)),
        ("sin descubrir pronto", training_priority(None, leaves_soon=True)),
        ("sin descubrir tarde", training_priority(None, leaves_soon=False)),
        ("insuficiente", training_priority(5, leaves_soon=True)),
        ("el resto", training_priority(4, leaves_soon=True)),
    ]
    assert [p for _, p in orden] == [1, 2, 3, 4, 5, 6, 7, 8, 9], orden


def test_al_excelente_no_le_afecta_el_plazo() -> None:
    """Un crack se aprovecha aunque le quede poco, y aunque le quede mucho."""
    assert training_priority(8, leaves_soon=True) == training_priority(
        8, leaves_soon=False
    )


def test_un_techo_ya_alcanzado_no_es_sin_descubrir() -> None:
    """No es que no se sepa: se sabe que no sube. Entrenarlo es tiempo tirado."""
    assert training_priority(None, leaves_soon=True, max_reached=True) == 9
    assert training_priority(9, leaves_soon=True, max_reached=True) == 9


def _canterano(nombre: str, dias: int, lectura: YouthSkillReading) -> YouthCandidate:
    return YouthCandidate(
        name=nombre, age_years_at_deadline=17, age_days_at_deadline=dias,
        skills={"scoring": lectura},
    )


def test_entre_dos_buenos_iguales_primero_el_que_se_va() -> None:
    candidatos = [
        _canterano("Se queda", 90, YouthSkillReading(current=7, maximum=7)),
        _canterano("Se va ya", 10, YouthSkillReading(current=7, maximum=7)),
    ]
    marcador = next(s for s in score_skills(candidatos) if s.skill == "scoring")
    assert [p.name for p in marcador.players] == ["Se va ya", "Se queda"]


def test_la_cola_completa_con_gente_de_todos_los_peldaños() -> None:
    candidatos = [
        _canterano("Malo", 10, YouthSkillReading(current=3, maximum=3)),
        _canterano("Insuficiente", 10, YouthSkillReading(current=5, maximum=5)),
        _canterano("Desconocido tarde", 90, YouthSkillReading(current=None, maximum=None)),
        _canterano("Desconocido pronto", 10, YouthSkillReading(current=None, maximum=None)),
        _canterano("Aceptable tarde", 90, YouthSkillReading(current=6, maximum=6)),
        _canterano("Aceptable pronto", 10, YouthSkillReading(current=6, maximum=6)),
        _canterano("Bueno tarde", 90, YouthSkillReading(current=7, maximum=7)),
        _canterano("Bueno pronto", 10, YouthSkillReading(current=7, maximum=7)),
        _canterano("Excelente", 90, YouthSkillReading(current=8, maximum=8)),
    ]
    marcador = next(s for s in score_skills(candidatos) if s.skill == "scoring")
    assert [p.name for p in marcador.players] == [
        "Excelente",
        "Bueno pronto",
        "Bueno tarde",
        "Aceptable pronto",
        "Aceptable tarde",
        "Desconocido pronto",
        "Desconocido tarde",
        "Insuficiente",
        "Malo",
    ]


def test_el_puntaje_de_la_habilidad_no_lo_toca_esta_cola() -> None:
    """La otra decision sigue igual: insuficiente y peores no puntuan."""
    candidatos = [_canterano("Insuficiente", 10, YouthSkillReading(current=5, maximum=5))]
    marcador = next(s for s in score_skills(candidatos) if s.skill == "scoring")
    assert marcador.score == 0.0
    assert marcador.players[0].priority == 8
