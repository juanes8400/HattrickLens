"""El glosario oficial de Hattrick, leído de `translations.xml` 1.2 (2026-09-15).

Lo que se vigila:

  * que el lector saca cada sección con claves estables,
  * que el español coincide palabra por palabra con lo que la app ya enseñaba
    --traducir no puede cambiar lo que ve quien usa la app en español--,
  * que el JSON guardado en el repositorio es lo que da el lector.
"""

import json
from pathlib import Path

from app.infrastructure.chpp.glosario import leer_translations

FIXTURES = Path(__file__).parent / "fixtures"
GLOSARIO = Path(__file__).resolve().parents[1] / "app" / "config" / "glosario"

#: Los niveles tal cual estaban escritos a mano en `frontend/src/utils/skillLevels.ts`.
NIVELES_QUE_YA_SE_VEIAN = [
    "nulo",
    "desastroso",
    "horrible",
    "pobre",
    "débil",
    "insuficiente",
    "aceptable",
    "bueno",
    "excelente",
    "formidable",
    "destacado",
    "brillante",
    "magnífico",
    "clase mundial",
    "sobrenatural",
    "titánico",
    "extraterrestre",
    "mítico",
    "mágico",
    "utópico",
    "divino",
]


def _leer(nombre: str) -> dict:
    return leer_translations((FIXTURES / nombre).read_bytes())


def test_el_ingles_trae_las_palabras_oficiales() -> None:
    g = _leer("translations_en.xml")
    assert g["idioma"] == {"id": 2, "nombre": "English (UK)"}
    assert g["habilidades"]["set_pieces"] == "Set Pieces"
    assert g["niveles"]["7"] == "solid"
    assert g["niveles"]["20"] == "divine"
    assert g["especialidades"]["8"] == "Support"
    assert g["tacticas"]["7"] == "Play Creatively"
    assert g["puestos"]["InnerMidfield"] == "Inner Midfielder"
    assert g["actitud"]["-1"] == "Play it Cool"
    assert g["entrenamientos"]["13"] == "Individual"
    assert g["etiquetas"]["especialidades"] == "Speciality"
    assert g["ligas"]["19"] == "Colombia"


def test_el_espanol_no_cambia_ni_una_palabra_de_los_niveles() -> None:
    g = _leer("translations_es.xml")
    assert g["idioma"]["id"] == 6
    assert [g["niveles"][str(i)] for i in range(21)] == NIVELES_QUE_YA_SE_VEIAN
    assert g["habilidades"]["stamina"] == "Resistencia"


def test_el_glosario_guardado_es_el_que_da_el_lector() -> None:
    for codigo, fixture in (("es", "translations_es.xml"), ("en", "translations_en.xml")):
        guardado = json.loads((GLOSARIO / f"{codigo}.json").read_text(encoding="utf-8"))
        leido = _leer(fixture)
        assert guardado["niveles"] == leido["niveles"]
        assert guardado["habilidades"] == leido["habilidades"]
