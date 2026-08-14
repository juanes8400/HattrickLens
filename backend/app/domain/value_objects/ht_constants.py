"""Constantes del juego Hattrick. Dominio puro, sin I/O.

Se mantienen aquí, y no hardcodeadas en la UI, para que backend, workers y
AI Assistant compartan una única fuente de verdad.
"""

# IDs de trainingType de CHPP DataTypes. 0 y 1 están marcados como deprecated
# por CHPP, pero se conservan para interpretar histórico o XML antiguos.
TRAINING_TYPES: dict[int, str] = {
    0: "General (obsoleto)",
    1: "Resistencia (obsoleto)",
    2: "Balón parado",
    3: "Defensa",
    4: "Anotación",
    5: "Lateral",
    6: "Anotación y balón parado",
    7: "Pases",
    8: "Jugadas",
    9: "Portería",
    10: "Pases (defensas y centrocampistas)",
    11: "Defensa (porteros, defensas y centrocampistas)",
    12: "Lateral (extremos y delanteros)",
}

# Skill principal que entrena cada tipo (para el motor de entrenamiento).
TRAINING_TARGET_SKILL: dict[int, str] = {
    1: "stamina",
    2: "set_pieces",
    3: "defending",
    4: "scoring",
    5: "winger",
    6: "scoring",
    7: "passing",
    8: "playmaking",
    9: "keeper",
    10: "passing",
    11: "defending",
    12: "winger",
}

SKILL_LABELS: dict[str, str] = {
    "keeper": "Portería",
    "defending": "Defensa",
    "playmaking": "Jugadas",
    "winger": "Lateral",
    "passing": "Pases",
    "scoring": "Anotación",
    "set_pieces": "Balón parado",
}

SPECIALTIES: dict[int, str] = {
    0: "",
    1: "Técnico",
    2: "Rápido",
    3: "Potente",
    4: "Imprevisible",
    5: "Cabeceador",
    6: "Estoico",
    8: "Influyente",
}

PLAYER_AGREEABILITY: dict[int, str] = {
    0: "antipática",
    1: "polémica",
    2: "agradable",
    3: "carismática",
    4: "popular",
    5: "querido compañero de equipo",
}
PLAYER_AGGRESSIVENESS: dict[int, str] = {
    0: "tranquila",
    1: "calmada",
    2: "equilibrada",
    3: "temperamental",
    4: "iracunda",
    5: "violenta",
}
PLAYER_HONESTY: dict[int, str] = {
    0: "infame",
    1: "deshonesto",
    2: "honesto",
    3: "justo",
    4: "honorable",
    5: "santito",
}

TEAM_SPIRIT: dict[int, str] = {
    0: "Como en la Guerra Fría",
    1: "Muy agresivos",
    2: "Tensos",
    3: "Susceptibles",
    4: "Serenos",
    5: "Calmados",
    6: "Contentos",
    7: "Encantados",
    8: "Eufóricos",
    9: "Por las nubes",
    10: "Paraíso en la Tierra",
}

CONFIDENCE: dict[int, str] = {
    0: "Inexistente",
    1: "Por los suelos",
    2: "Muy baja",
    3: "Baja",
    4: "Decente",
    5: "Sólida",
    6: "Alta",
    7: "Muy alta",
    8: "Exagerada",
    9: "Desmedida",
}

SKILL_LEVELS: tuple[str, ...] = (
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
)


def skill_name(level: int) -> str:
    if level < 0:
        return "?"
    if level < len(SKILL_LEVELS):
        return SKILL_LEVELS[level]
    return f"divino+{level - 20}"


def training_name(type_id: int) -> str:
    return TRAINING_TYPES.get(type_id, f"tipo {type_id}")


def training_skill_name(type_id: int) -> str:
    """Nombre de la HABILIDAD que entrena un tipo, no el nombre completo de
    Hattrick con su complemento de posiciones — pedido explícitamente
    2026-08-04 para el desglose "por Entrenamiento" del saldo por jugador
    ("Pases (defensas y centrocampistas)" debe leerse "Pases", no el nombre
    completo). Cae de vuelta al nombre crudo de `training_name` para los
    tipos obsoletos (0/1) que no entrenan ninguna de las 7 habilidades de
    `SKILL_LABELS` — no hay una "habilidad" limpia a la que mapearlos."""
    skill = TRAINING_TARGET_SKILL.get(type_id)
    if skill is None:
        return training_name(type_id)
    return SKILL_LABELS.get(skill, training_name(type_id))


def training_target(type_id: int) -> str | None:
    return TRAINING_TARGET_SKILL.get(type_id)


# PositionCode de matchlineup.xml observado en fixtures reales.
MATCH_POSITION_NAMES: dict[int, str] = {
    1: "Portero",
    2: "Lateral derecho",
    3: "Defensa central derecho",
    4: "Defensa central medio",
    5: "Defensa central izquierdo",
    6: "Lateral izquierdo",
    7: "Extremo derecho",
    8: "Interior derecho",
    9: "Interior medio",
    10: "Interior izquierdo",
    11: "Extremo izquierdo",
    12: "Delantero derecho",
    13: "Delantero medio",
    14: "Delantero izquierdo",
    # Verificado en vivo (matchlineup.xml real, teamID 3357872): suplentes
    # que quedaron en el banco sin entrar (RatingStars=0). Sigue la misma
    # familia de códigos que MATCH_ROLE_NAMES 17-24 (especialista de balón
    # parado, capitán, entró por el titular N...) y la terminología real de
    # Hattrick para las dos plazas de suplente sin categoría fija.
    15: "Suplente extra 1",
    16: "Suplente extra 2",
}
MATCH_POSITION_KEEPER = 1


def match_position_name(code: int) -> str:
    return MATCH_POSITION_NAMES.get(code, f"posición {code}")


MATCH_TYPE_LEAGUE = 1
MATCH_TYPE_QUALIFICATION = 2
MATCH_TYPE_CUP = 3
MATCH_TYPE_FRIENDLY = 4
MATCH_TYPE_FRIENDLY_CUP_RULES = 5
MATCH_TYPE_MASTERS = 7
MATCH_TYPE_INTERNATIONAL_FRIENDLY = 8
MATCH_TYPE_INTERNATIONAL_FRIENDLY_CUP_RULES = 9
MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE = 10
MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES = 11
MATCH_TYPE_NATIONAL_TEAM_FRIENDLY = 12
MATCH_TYPE_TOURNAMENT_LEAGUE = 50
MATCH_TYPE_TOURNAMENT_PLAYOFF = 51
MATCH_TYPE_DUEL = 61
MATCH_TYPE_LADDER = 62
MATCH_TYPE_PREPARATION = 80
MATCH_TYPE_YOUTH_LEAGUE = 100
MATCH_TYPE_YOUTH_FRIENDLY = 101
MATCH_TYPE_YOUTH_FRIENDLY_CUP_RULES = 103
MATCH_TYPE_YOUTH_INTERNATIONAL_FRIENDLY = 105
MATCH_TYPE_YOUTH_INTERNATIONAL_FRIENDLY_CUP_RULES = 106

MATCH_TYPE_NAMES: dict[int, str] = {
    MATCH_TYPE_LEAGUE: "Liga",
    MATCH_TYPE_QUALIFICATION: "Promoción",
    MATCH_TYPE_CUP: "Copa",
    MATCH_TYPE_FRIENDLY: "Amistoso",
    MATCH_TYPE_FRIENDLY_CUP_RULES: "Amistoso (reglas de copa)",
    MATCH_TYPE_MASTERS: "Hattrick Masters",
    MATCH_TYPE_INTERNATIONAL_FRIENDLY: "Amistoso internacional",
    MATCH_TYPE_INTERNATIONAL_FRIENDLY_CUP_RULES: "Amistoso internacional (reglas de copa)",
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE: "Selección nacional",
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES: "Selección nacional (reglas de copa)",
    MATCH_TYPE_NATIONAL_TEAM_FRIENDLY: "Amistoso de selección",
    MATCH_TYPE_TOURNAMENT_LEAGUE: "Torneo: liga",
    MATCH_TYPE_TOURNAMENT_PLAYOFF: "Torneo: playoff",
    MATCH_TYPE_DUEL: "Duelo",
    MATCH_TYPE_LADDER: "Escalera",
    MATCH_TYPE_PREPARATION: "Preparación",
    MATCH_TYPE_YOUTH_LEAGUE: "Liga juvenil",
    MATCH_TYPE_YOUTH_FRIENDLY: "Amistoso juvenil",
    MATCH_TYPE_YOUTH_FRIENDLY_CUP_RULES: "Amistoso juvenil (reglas de copa)",
    MATCH_TYPE_YOUTH_INTERNATIONAL_FRIENDLY: "Amistoso juvenil internacional",
    MATCH_TYPE_YOUTH_INTERNATIONAL_FRIENDLY_CUP_RULES:
        "Amistoso juvenil internacional (reglas de copa)",
}

NON_OFFICIAL_MATCH_TYPES: frozenset[int] = frozenset({
    MATCH_TYPE_TOURNAMENT_LEAGUE,
    MATCH_TYPE_TOURNAMENT_PLAYOFF,
    MATCH_TYPE_DUEL,
    MATCH_TYPE_LADDER,
    MATCH_TYPE_PREPARATION,
})
FRIENDLY_MATCH_TYPES: frozenset[int] = frozenset({
    MATCH_TYPE_FRIENDLY,
    MATCH_TYPE_FRIENDLY_CUP_RULES,
    MATCH_TYPE_INTERNATIONAL_FRIENDLY,
    MATCH_TYPE_INTERNATIONAL_FRIENDLY_CUP_RULES,
    MATCH_TYPE_NATIONAL_TEAM_FRIENDLY,
})


def is_competitive_match_type(match_type: int) -> bool:
    return match_type not in NON_OFFICIAL_MATCH_TYPES and match_type not in FRIENDLY_MATCH_TYPES


def is_friendly_match_type(match_type: int) -> bool:
    return match_type in FRIENDLY_MATCH_TYPES


def match_type_name(match_type: int) -> str:
    return MATCH_TYPE_NAMES.get(match_type, f"partido tipo {match_type}")


MATCH_POSITION_WINGBACK: frozenset[int] = frozenset({2, 6})
MATCH_POSITION_CENTRAL_DEFENDER: frozenset[int] = frozenset({3, 4, 5})
MATCH_POSITION_INNER_MIDFIELDER: frozenset[int] = frozenset({8, 9, 10})
MATCH_POSITION_WINGER: frozenset[int] = frozenset({7, 11})
MATCH_POSITION_FORWARD: frozenset[int] = frozenset({12, 13, 14})

# Reglas reales del marcaje individual (docs/reference/MAN_MARKING_RULES.md):
# cualquiera de {lateral, defensa central, interior} puede marcar a
# cualquiera de {extremo, defensa central, interior} rival — es SIEMPRE
# legal. MAN_MARKING_PROXIMITY es solo la combinación "cerca" (-50%, la más
# eficiente); cualquier otra combinación legal es "lejos" (-65%) — sigue
# siendo una orden válida, solo menos eficiente.
MAN_MARKING_PROXIMITY: dict[frozenset[int], frozenset[int]] = {
    MATCH_POSITION_WINGBACK: MATCH_POSITION_WINGER,
    MATCH_POSITION_CENTRAL_DEFENDER: MATCH_POSITION_FORWARD,
    MATCH_POSITION_INNER_MIDFIELDER: MATCH_POSITION_INNER_MIDFIELDER,
}
MAN_MARKING_ELIGIBLE_MARKERS: frozenset[int] = (
    MATCH_POSITION_WINGBACK | MATCH_POSITION_CENTRAL_DEFENDER | MATCH_POSITION_INNER_MIDFIELDER
)
MAN_MARKING_ELIGIBLE_TARGETS: frozenset[int] = (
    MATCH_POSITION_WINGER | MATCH_POSITION_FORWARD | MATCH_POSITION_INNER_MIDFIELDER
)

TACTIC_TYPES: dict[int, str] = {
    0: "Normal",
    1: "Presionar",
    2: "Contraataques",
    3: "Atacar por el centro",
    4: "Atacar por las bandas",
    7: "Jugar creativamente",
    8: "Tiros lejanos",
}


def tactic_type_name(code: int) -> str:
    return TACTIC_TYPES.get(code, f"táctica {code}")


TEAM_ATTITUDE: dict[int, str] = {
    -1: "Jugar relajados",
    0: "Normal",
    1: "Partido de la temporada",
}


def team_attitude_name(code: int) -> str:
    return TEAM_ATTITUDE.get(code, f"actitud {code}")


WEATHER: dict[int, str] = {
    0: "Lluvia",
    1: "Cubierto",
    2: "Parcialmente nublado",
    3: "Soleado",
}


def weather_name(code: int) -> str:
    return WEATHER.get(code, f"clima {code}")


MATCH_BEHAVIOUR: dict[int, str] = {
    -1: "Sin cambio",
    0: "Normal",
    1: "Ofensivo",
    2: "Defensivo",
    3: "Hacia el medio",
    4: "Hacia la banda",
    5: "Delantero extra",
    6: "Interior extra",
    7: "Defensa extra",
}


def match_behaviour_name(code: int) -> str:
    return MATCH_BEHAVIOUR.get(code, f"comportamiento {code}")


PLAYER_CATEGORY: dict[int, str] = {
    0: "Sin categoría",
    1: "Portero",
    2: "Lateral",
    3: "Defensa central",
    4: "Extremo",
    5: "Interior",
    6: "Delantero",
    7: "Suplente",
    8: "Reserva",
    9: "Extra 1",
    10: "Extra 2",
}


def player_category_name(code: int) -> str:
    return PLAYER_CATEGORY.get(code, f"categoría {code}")


STAFF_TYPES: dict[int, str] = {
    1: "Asistente de entrenador",
    2: "Médico",
    3: "Portavoz",
    4: "Psicólogo deportivo",
    5: "Entrenador de forma",
    6: "Director financiero",
    7: "Asistente táctico",
}


def staff_type_name(code: int) -> str:
    return STAFF_TYPES.get(code, f"staff {code}")


# 2026-08-12, corrección: `club.xml` dejó de traer los niveles agregados por
# puesto (`AssistantTrainerLevels` y hermanos) — verificado en vivo, la
# versión actual (1.1) sólo trae `<Specialists>` (booleanos) y `<YouthSquad>`.
# El desglose real, persona por persona, siempre vivió en `stafflist.xml`
# (`StaffType`/`StaffLevel` de cada `<Staff>`) — este mapa agrupa esos
# miembros reales en la misma columna de `StaffSnapshot` que antes llenaba
# (mal, con datos obsoletos) el fichero `club`.
STAFF_TYPE_TO_FIELD: dict[int, str] = {
    1: "assistant_trainer_levels",
    2: "medic_levels",
    3: "spokesperson_levels",
    4: "sport_psychologist_levels",
    5: "form_coach_levels",
    6: "financial_director_levels",
    7: "tactical_assistant_levels",
}


# MatchRoleID de CHPP DataTypes, usado en LastMatch y ordenes modernas.
MATCH_ROLE_NAMES: dict[int, str] = {
    100: "Portero",
    101: "Lateral derecho",
    102: "Defensa central derecho",
    103: "Defensa central medio",
    104: "Defensa central izquierdo",
    105: "Lateral izquierdo",
    106: "Extremo derecho",
    107: "Interior derecho",
    108: "Interior medio",
    109: "Interior izquierdo",
    110: "Extremo izquierdo",
    111: "Delantero derecho",
    112: "Delantero medio",
    113: "Delantero izquierdo",
    114: "Suplente (portero)",
    115: "Suplente (defensa)",
    116: "Suplente (interior)",
    117: "Suplente (extremo)",
    118: "Suplente (delantero)",
    119: "Suplente (lateral)",
    120: "Suplente (extra)",
    200: "Suplente (portero)",
    201: "Suplente (defensa central)",
    202: "Suplente (lateral)",
    203: "Suplente (interior)",
    204: "Suplente (delantero)",
    205: "Suplente (extremo)",
    206: "Suplente (extra)",
    207: "Backup (portero)",
    208: "Backup (defensa central)",
    209: "Backup (lateral)",
    210: "Backup (interior)",
    211: "Backup (delantero)",
    212: "Backup (extremo)",
    213: "Backup (extra)",
    17: "Especialista balón parado",
    18: "Capitán",
    19: "Entró por el titular 1",
    20: "Entró por el titular 2",
    21: "Entró por el titular 3",
    22: "Lanzador de penalti 1",
    23: "Lanzador de penalti 2",
    24: "Lanzador de penalti 3",
    25: "Lanzador de penalti 4",
    26: "Lanzador de penalti 5",
    27: "Lanzador de penalti 6",
    28: "Lanzador de penalti 7",
    29: "Lanzador de penalti 8",
    30: "Lanzador de penalti 9",
    31: "Lanzador de penalti 10",
    32: "Lanzador de penalti 11",
    33: "Expulsado 1",
    34: "Expulsado 2",
    35: "Expulsado 3",
}


def match_role_name(code: int) -> str:
    return MATCH_ROLE_NAMES.get(code, f"posición {code} (sin traducir)")


# 2026-08-09, corregido tras un caso real: `matchlineup.xml` sirve un
# esquema DISTINTO de `RoleID` según la versión pedida. Sin `version`
# explícito, CHPP responde v1.2 — ahí `RoleID` es solo un índice secuencial
# (1, 2, 3... orden de aparición en el XML, sin significado táctico) y la
# única columna con la posición real es `PositionCode` (1-16,
# MATCH_POSITION_*). Pidiendo `version=1.4` (verificado en vivo, matchID
# 770453114, playerID 468921494: Alberto Gutiérrez Caviedes salió con
# RoleID=112 = "Delantero medio" — jugó de delantero, no de interior como
# decía su PositionCode v1.2), `RoleID` pasa a usar el MISMO esquema 100+
# que `MATCH_ROLE_NAMES` (LastMatch de playerdetails.xml). Estos frozensets
# agrupan ese esquema 100+ igual que los MATCH_POSITION_* de arriba agrupan
# el 1-16 — para cuando el llamador pide v1.4+ y por tanto lee `role_id`
# como posición real, no `position_code` (que a v1.4+ es redundante y a
# v1.5+ directamente desaparece del XML).
MATCH_ROLE_KEEPER: frozenset[int] = frozenset({100})
MATCH_ROLE_WINGBACK: frozenset[int] = frozenset({101, 105})
MATCH_ROLE_CENTRAL_DEFENDER: frozenset[int] = frozenset({102, 103, 104})
MATCH_ROLE_WINGER: frozenset[int] = frozenset({106, 110})
MATCH_ROLE_INNER_MIDFIELDER: frozenset[int] = frozenset({107, 108, 109})
MATCH_ROLE_FORWARD: frozenset[int] = frozenset({111, 112, 113})

# 2026-08-09, pedido explícitamente: siglas cortas para "Última semana" en
# Posiciones — el lado (derecho/izquierdo/medio) no importa, pero SÍ la
# orden individual real (Ofensivo/Defensivo/Hacia el medio/Hacia la
# banda), que antes no se mostraba porque vive en un campo aparte
# (`Behaviour` de matchlineup.xml, no `LastMatch` de playerdetails.xml).
# Los cupos "extra" (Behaviour 5/6/7: delantero/interior/defensa extra) y
# "Normal"/"Sin cambio" (0/-1) no llevan sufijo — solo se muestra la
# posición base.
MATCH_ROLE_SHORT_LABELS: dict[frozenset[int], str] = {
    MATCH_ROLE_KEEPER: "Portero",
    MATCH_ROLE_WINGBACK: "DL",
    MATCH_ROLE_CENTRAL_DEFENDER: "DC",
    MATCH_ROLE_WINGER: "Ex",
    MATCH_ROLE_INNER_MIDFIELDER: "Medio",
    MATCH_ROLE_FORWARD: "Del",
}
MATCH_BEHAVIOUR_SHORT_SUFFIXES: dict[int, str] = {
    1: "of",
    2: "def",
    3: "h M",
    4: "h L",
}


def match_role_short_label(role_id: int, behaviour: int | None) -> str:
    base = next(
        (label for roles, label in MATCH_ROLE_SHORT_LABELS.items() if role_id in roles),
        None,
    )
    if base is None:
        return match_role_name(role_id)
    suffix = MATCH_BEHAVIOUR_SHORT_SUFFIXES.get(behaviour) if behaviour is not None else None
    return f"{base} {suffix}" if suffix else base
