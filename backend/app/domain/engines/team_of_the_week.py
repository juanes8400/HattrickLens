"""Mejor alineación (semana/temporada) — pedido explícitamente 2026-08-08,
tras comparar con Hattrick Control.

Mismo criterio que el "Equipo de la semana" oficial de Hattrick: por cada
partido ya jugado se conoce el rating real de cada titular
(`matchlineup.xml` — público incluso para un rival, ver comentario en su
parser: un partido ya finalizado es un hecho público permanente, no un
histórico de cuenta ajena). Los roles titulares se agrupan en 4 bloques
(portero, defensas, medios, delanteros) y en cada bloque se eligen los N
de mayor rating de todo el rango pedido (una jornada o toda la temporada),
sin importar el equipo — así un rival puede colarse en tu propio "equipo
ideal" si tuvo la mejor actuación real.

2026-08-08 (3ª corrección): no hay un reparto fijo de cupos — la
herramienta oficial de Hattrick Control deja elegir la formación
(4-4-2, 3-5-2, 3-4-3, 4-5-1, 4-3-3, 5-3-2, 5-4-1) y reparte los 10 cupos
de campo según esa formación. `FORMATIONS` replica esa tabla.

2026-08-09 (4ª corrección, bug real): los bloques se armaban con
`PositionCode` de matchlineup.xml pedido sin `version` (CHPP sirve ~1.2 en
ese caso), donde ese campo es solo la "casilla de formación" del arranque
— cuando dos jugadores comparten formación (frecuente en mediocampos con
más de un interior) ambos quedan con el mismo código aunque uno funcione
de delantero real, y ningún suplente que entró a mitad de partido tiene
código fiable. Resultado en vivo: "Delanteros" salía vacío en 8/8
alineaciones de una jornada completa — estadísticamente imposible si el
dato fuera bueno. Pidiendo `version=2.1` explícito (matchID 770453114,
playerID 468921494 confirmado: RoleID=112="Delantero medio" — jugó de
delantero real, entrando como suplente a los 32'), `RoleID` pasa a ser el
puesto REAL (MATCH_ROLE_*, esquema 100+, MATCH_ROLE_NAMES) del `<Lineup>`
final — que en 2.1 ya incorpora el resultado de cada `<Substitution>`, así
que hasta un suplente que entró en el minuto 80 queda con su posición real,
no con "-1, desconocido". Este motor ahora agrupa por `role_id` (no
`position_code`)."""

from dataclasses import dataclass

from app.domain.value_objects.formations import (  # noqa: F401
    DEFAULT_FORMATION,
    LINE_COUNTS,
    # Se RE-EXPORTAN: hay quien los importa desde aqui, no de `formations`.
    # Ruff los ve sin usar en este fichero y los borro; la suite se cayo con
    # 18 modulos sin poder importar. De ahi el `noqa`.
    MAX_CENTRAL_DEFENDERS,
    MAX_INNER_MIDFIELDERS,
    line_splits,
    resolve_split,
)
from app.domain.value_objects.ht_constants import (
    MATCH_ROLE_CENTRAL_DEFENDER,
    MATCH_ROLE_FORWARD,
    MATCH_ROLE_INNER_MIDFIELDER,
    MATCH_ROLE_KEEPER,
    MATCH_ROLE_WINGBACK,
    MATCH_ROLE_WINGER,
)

# `role_id` aquí es el `RoleID` de matchlineup.xml pedido con
# `version=2.1` (100+, verificado contra fixtures reales — MATCH_ROLE_* en
# ht_constants.py), NO el `PositionCode` (1-16) que servía sin versión
# explícita — ver docstring del módulo. "Defensa" agrupa laterales Y
# centrales, y "medios" agrupa extremos E interiores: la composición real
# del Equipo de la Semana no fija cuántos de cada sub-rol, solo reparte
# cupos entre los códigos posibles de cada bloque.
KEEPER_ROLES = MATCH_ROLE_KEEPER
DEFENSE_ROLES = MATCH_ROLE_WINGBACK | MATCH_ROLE_CENTRAL_DEFENDER
MIDFIELD_ROLES = MATCH_ROLE_WINGER | MATCH_ROLE_INNER_MIDFIELDER
FORWARD_ROLES = MATCH_ROLE_FORWARD

# El catálogo y los repartos viven en `value_objects/formations.py`, junto con
# los del optimizador de Alineación: describen lo mismo y separados acabarían
# significando cosas distintas.
FORMATIONS = LINE_COUNTS

SLOT_LABELS: dict[str, str] = {
    "keeper": "Portero",
    "defense": "Defensas",
    "midfield": "Medios",
    "forward": "Delanteros",
}


@dataclass(frozen=True)
class LineupPlayer:
    ht_player_id: int
    name: str
    team_ht_id: int
    team_name: str
    role_id: int
    rating_stars: float
    ht_match_id: int


@dataclass(frozen=True)
class SlotPlayer:
    ht_player_id: int
    name: str
    team_ht_id: int
    team_name: str
    rating_stars: float
    role_id: int
    ht_match_id: int


def best_team(
    players: list[LineupPlayer],
    formation: str = DEFAULT_FORMATION,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> dict[str, list[SlotPlayer]]:
    """Un mismo jugador puede aparecer en varios partidos del rango
    (temporada) — se cuenta solo su MEJOR actuación, nunca ocupa dos cupos
    del mismo bloque él solo.

    Un 0.0 en `rating_stars` no es una actuación mala, es "no jugó de
    verdad" (lesión antes del pitazo, salió sin pisar la cancha, etc.) —
    nunca puede ser "el mejor" de nada. Si un bloque se queda sin
    candidatos reales, se devuelve incompleto en vez de rellenarlo con un
    0.0 (mismo criterio que "sin suficientes candidatos": mejor una fila
    de menos que un dato inventado)."""
    defense_count, midfield_count, forward_count = FORMATIONS.get(
        formation, FORMATIONS[DEFAULT_FORMATION]
    )
    # 2026-08-19: los cupos se reparten además por SUB-ROL, como en los
    # selectores de Hattrick Control. Antes se cogían los cinco mejores
    # defensas dieran igual laterales o centrales, y un once ideal podía
    # salir con cuatro centrales y ningún lateral: una alineación que el
    # juego no deja poner.
    centrales, interiores = resolve_split(formation, central_defenders, inner_midfielders)
    slots: tuple[tuple[str, frozenset[int], int], ...] = (
        ("keeper", KEEPER_ROLES, 1),
        ("central_defender", MATCH_ROLE_CENTRAL_DEFENDER, centrales),
        ("wingback", MATCH_ROLE_WINGBACK, defense_count - centrales),
        ("inner_midfield", MATCH_ROLE_INNER_MIDFIELDER, interiores),
        ("winger", MATCH_ROLE_WINGER, midfield_count - interiores),
        ("forward", FORWARD_ROLES, forward_count),
    )
    result: dict[str, list[SlotPlayer]] = {}
    for key, roles, count in slots:
        # Cero cupos es cero jugadores. El corte de abajo compara DESPUÉS de
        # añadir, así que con count=0 no se cumplía nunca y la línea se
        # llenaba con toda la liga: el 5-5-0 devolvía 16 delanteros
        # (2026-08-19).
        if count <= 0:
            result[key] = []
            continue
        candidates = sorted(
            (p for p in players if p.role_id in roles and p.rating_stars > 0),
            key=lambda p: -p.rating_stars,
        )
        chosen: list[SlotPlayer] = []
        seen: set[int] = set()
        for p in candidates:
            if p.ht_player_id in seen:
                continue
            seen.add(p.ht_player_id)
            chosen.append(
                SlotPlayer(
                    ht_player_id=p.ht_player_id,
                    name=p.name,
                    team_ht_id=p.team_ht_id,
                    team_name=p.team_name,
                    rating_stars=p.rating_stars,
                    role_id=p.role_id,
                    ht_match_id=p.ht_match_id,
                )
            )
            if len(chosen) == count:
                break
        result[key] = chosen
    # Las cuatro líneas de siempre, para quien solo quiera pintarlas: el
    # detalle por sub-rol se conserva al lado, que es lo que permite poner a
    # los de banda en las orillas de la cancha.
    result["defense"] = result["central_defender"] + result["wingback"]
    result["midfield"] = result["inner_midfield"] + result["winger"]
    return result
