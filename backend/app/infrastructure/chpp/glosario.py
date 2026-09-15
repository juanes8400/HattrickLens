"""`translations.xml` 1.2: el vocabulario oficial de Hattrick en un idioma.

2026-09-15, para traducir la app. Hattrick publica en este fichero las palabras
que usa el propio juego --habilidades, niveles, especialidades, carácter,
tácticas, puestos, espíritu, confianza, afición, países-- y es lo que se espera
que use una aplicación CHPP: que quien juega en inglés vea en HT Lens las
mismas palabras que en Hattrick.

Sólo lee. Quien lo descarga y lo guarda es `scripts/generar_glosario.py`.
"""

from typing import Any
from xml.etree.ElementTree import Element  # noqa: S405, sólo el tipo; se lee con defusedxml

from defusedxml import ElementTree

#: El `Type` de cada habilidad en el XML, con la clave que usa la app.
HABILIDADES: dict[str, str] = {
    "Keeper": "keeper",
    "Stamina": "stamina",
    "Defender": "defending",
    "Playmaker": "playmaking",
    "Winger": "winger",
    "Scorer": "scoring",
    "Kicker": "set_pieces",
    "Passer": "passing",
    "Experience": "experience",
    "LeaderShip": "leadership",
    "Form": "form",
}

#: Cada sección de `<Texts>` con la clave que lleva en el glosario. Todas son
#: listas de `<Level>` o `<Item>` con `Value` o `Type`.
SECCIONES: dict[str, str] = {
    "SkillSubLevels": "subniveles",
    "PlayerSpecialties": "especialidades",
    "PlayerAgreeability": "simpatia",
    "PlayerAgressiveness": "agresividad",
    "PlayerHonesty": "honradez",
    "TacticTypes": "tacticas",
    "MatchPositions": "puestos",
    "RatingSectors": "sectores",
    "TeamAttitude": "actitud",
    "TeamSpirit": "espiritu",
    "Confidence": "confianza",
    "TrainingTypes": "entrenamientos",
    "Sponsors": "patrocinadores",
    "FanMood": "aficion",
    "FanMatchExpectations": "expectativas_partido",
    "FanSeasonExpectations": "expectativas_temporada",
}


def _texto(nodo: Element | None) -> str:
    return (nodo.text or "").strip() if nodo is not None else ""


def leer_translations(xml: bytes) -> dict[str, Any]:
    """El glosario de un idioma, con claves estables para la app.

    `niveles` va por número en texto («0» a «20») y cada sección por su
    `Value` o su `Type`, tal cual los da Hattrick. `etiquetas` guarda el
    `Label` de cada sección («Speciality», «Tactic»...). `ligas` son los
    nombres de los países en ese idioma, por `LeagueId`.
    """
    raiz = ElementTree.fromstring(xml)
    textos = raiz.find("Texts")
    if textos is None:
        raise ValueError("translations.xml sin <Texts>")
    idioma = raiz.find("Language")

    glosario: dict[str, Any] = {
        "idioma": {
            "id": int(idioma.get("Id", "0")) if idioma is not None else 0,
            "nombre": _texto(idioma),
        },
        "habilidades": {},
        "niveles": {},
        "etiquetas": {},
    }
    for habilidad in textos.iterfind("SkillNames/Skill"):
        clave = HABILIDADES.get(habilidad.get("Type", ""))
        if clave is not None:
            glosario["habilidades"][clave] = _texto(habilidad)
    for nivel in textos.iterfind("SkillLevels/Level"):
        glosario["niveles"][nivel.get("Value", "")] = _texto(nivel)

    for etiqueta_xml, clave in SECCIONES.items():
        seccion = textos.find(etiqueta_xml)
        if seccion is None:
            continue
        label = seccion.get("Label")
        if label:
            glosario["etiquetas"][clave] = label
        glosario[clave] = {
            (hijo.get("Value") or hijo.get("Type") or ""): _texto(hijo) for hijo in seccion
        }

    glosario["ligas"] = {
        (liga.findtext("LeagueId") or "").strip(): (
            liga.findtext("LanguageLeagueName") or ""
        ).strip()
        for liga in textos.iterfind("LeagueNames/League")
    }
    return glosario
