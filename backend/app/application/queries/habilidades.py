"""Habilidades: qué tiene la plantilla, dónde le falta y qué subida rinde más.

Tres respuestas sobre la plantilla ENTERA, habilidad por habilidad, que ni la
ficha de un jugador ni el plan de entrenamiento dan (2026-09-14, pedido del
usuario):

- **El mapa**: el nivel de cada jugador en cada habilidad.
- **La profundidad**: si cae el mejor en una habilidad, cuánto se pierde.
- **El cuello de botella**: el sector que peor queda frente a la serie, con
  la media de los últimos partidos oficiales de cada equipo, y la subida del
  once titular que más le aporta según la tabla de contribución por puesto del
  Manual no Escrito (`team_rating_engine`).

La lógica va en funciones puras, sin base de datos, para poder probarla sola.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.flor_de_fuerza import SectoresDeEquipo, sectores_de_la_serie
from app.domain.engines.position_engine import rate
from app.domain.engines.team_rating_engine import (
    OVERCROWDING_PENALTY,
    POSITION_SECTOR_CONTRIBUTION,
)
from app.domain.value_objects.formations import (
    LINE_COUNTS,
    central_defender_options,
    inner_midfielder_options,
    resolve_split,
    slots_for,
)
from app.domain.value_objects.ht_constants import SPECIALTIES, is_competitive_match_type
from app.infrastructure.db import models as m

#: Clave, nombre y sigla de cada habilidad, en el orden de la ficha de Hattrick.
HABILIDADES: tuple[tuple[str, str, str], ...] = (
    ("keeper", "Portería", "Por"),
    ("defending", "Defensa", "Def"),
    ("playmaking", "Jugadas", "Jug"),
    ("winger", "Lateral", "Lat"),
    ("passing", "Pases", "Pas"),
    ("scoring", "Anotación", "Ano"),
    ("set_pieces", "Balón parado", "BP"),
)
NOMBRE = {k: n for k, n, _ in HABILIDADES}
SIGLA_DE_HABILIDAD = {k: s for k, _, s in HABILIDADES}


@dataclass
class QuienSostiene:
    """Un jugador que sostiene un sector, en piezas.

    La frase junta va en ``Sector.who`` y se queda; esto es lo mismo sin
    juntar, para que la sigla se pueda traducir sola al salir.
    """

    player: str
    sigla: str
    nivel: int


EXCELENTE = 8
MAGNIFICO = 12
#: Por debajo de débil en la habilidad principal no se es recambio del puesto.
MINIMO_PARA_EL_PUESTO = 4

#: El puesto de Hattrick (código de la alineación) en el grupo del motor.
GRUPO_DEL_PUESTO: dict[int, str] = {
    100: "keeper",
    101: "wingback",
    105: "wingback",
    102: "central_defender",
    103: "central_defender",
    104: "central_defender",
    106: "winger",
    110: "winger",
    107: "inner_midfield",
    108: "inner_midfield",
    109: "inner_midfield",
    111: "forward",
    112: "forward",
    113: "forward",
}
ORDEN_DE_GRUPOS = ("keeper", "central_defender", "wingback", "inner_midfield", "winger", "forward")
SIGLA = {
    "keeper": "POR",
    "central_defender": "DC",
    "wingback": "LAT",
    "inner_midfield": "INT",
    "winger": "EXT",
    "forward": "DEL",
}
#: Los nombres de los puestos como los llama Hattrick: «Defensa Lateral» y
#: «Mediocentro», no «Lateral» ni «Interior» (2026-09-14, pedido del usuario).
ETIQUETA = {
    "keeper": "Portero",
    "central_defender": "Defensa Central",
    "wingback": "Defensa Lateral",
    "inner_midfield": "Mediocentro",
    "winger": "Extremo",
    "forward": "Delantero",
}
PLURAL = {
    "keeper": "Porteros",
    "central_defender": "Defensas Centrales",
    "wingback": "Defensas Laterales",
    "inner_midfield": "Mediocentros",
    "winger": "Extremos",
    "forward": "Delanteros",
}
#: La habilidad que define cada puesto: la que el mapa marca con borde.
HABILIDAD_DEL_PUESTO = {
    "keeper": "keeper",
    "central_defender": "defending",
    "wingback": "defending",
    "inner_midfield": "playmaking",
    "winger": "winger",
    "forward": "scoring",
}
#: La orden individual (0 normal, 1 ofensivo, 2 defensivo, 3 hacia el centro,
#: 4 hacia la banda) cambia cuánto aporta el jugador a cada sector.
VARIANTE: dict[tuple[str, int], str] = {
    ("central_defender", 1): "central_defender_offensive",
    ("central_defender", 4): "central_defender_towards_wing",
    ("wingback", 1): "wingback_offensive",
    ("wingback", 2): "wingback_defensive",
    ("wingback", 3): "wingback_towards_middle",
    ("inner_midfield", 1): "inner_midfield_offensive",
    ("inner_midfield", 2): "inner_midfield_defensive",
    ("inner_midfield", 4): "inner_midfield_towards_wing",
    ("winger", 1): "winger_offensive",
    ("winger", 2): "winger_defensive",
    ("winger", 3): "winger_towards_middle",
    ("forward", 2): "forward_defensive",
    ("forward", 4): "forward_towards_wing",
}
#: Los sectores de la pantalla en los del motor.
SECTORES_DEL_MOTOR: dict[str, tuple[str, ...]] = {
    "defensa": ("central_def", "lateral_def"),
    "mediocampo": ("midfield",),
    "ataque": ("central_att", "lateral_att"),
}


@dataclass
class Jugador:
    """Lo que la lógica necesita de un jugador; se arma desde la base."""

    ht_player_id: int
    name: str
    short_name: str
    age: int
    tsi: int
    skills: dict[str, int]
    specialty: int = 0
    injured: bool = False
    position_code: int | None = None
    behaviour: int | None = None
    in_lineup: bool = False
    #: De donde es, para la bandera de la tabla. El codigo sale del mundo
    #: (`country_code`) y el nombre de la liga natal, de la ficha: son las dos
    #: mismas fuentes que usa la pantalla de Posiciones.
    country_code: str | None = None
    native_league_name: str | None = None
    #: Lo que el motor de Posiciones usa además de las habilidades: forma,
    #: condición, experiencia, fidelidad, liderazgo y especialidad.
    motor: dict[str, Any] = field(default_factory=dict)

    @property
    def grupo(self) -> str | None:
        return GRUPO_DEL_PUESTO.get(self.position_code or 0)


@dataclass
class FilaJugador:
    ht_player_id: int
    name: str
    age: int
    tsi: int
    position: str | None
    position_label: str | None
    position_skill: str | None
    skills: dict[str, int]
    specialty: str
    injured: bool
    in_lineup: bool
    country_code: str | None
    native_league_name: str | None


@dataclass
class Candidato:
    ht_player_id: int
    name: str
    #: Rendimiento en el puesto: el mismo índice de la pantalla Posiciones.
    rating: float
    #: La habilidad principal del puesto, para leerlo también en niveles.
    skill_level: int


@dataclass
class Profundidad:
    """Un puesto de la última formación oficial y su recambio real."""

    key: str
    label: str
    #: Cuántos jugaron de titulares en ese puesto.
    starters: int
    skill_label: str
    best: Candidato | None
    #: El mejor del BANQUILLO en ese puesto, no el segundo mejor de la plantilla.
    substitute: Candidato | None
    #: Quién entraría después, si el suplente ya está tapando otro puesto.
    next_substitute: Candidato | None
    #: Cuánto rendimiento se pierde si el suplente entra por el mejor, en %.
    drop_pct: float | None
    #: Otros puestos cuyo recambio es el mismo jugador: no puede tapar los dos.
    also_covers: list[str]
    tone: str


@dataclass
class Sector:
    key: str
    label: str
    #: Media del sector en los últimos partidos oficiales.
    rating: float
    #: Dónde queda en la serie: 0 = el peor, 100 = el mejor.
    series_position: float
    #: Ventaja sobre el mejor rival del sector, en %. Negativa = va por detrás.
    margin_pct: float
    best_rival: str
    #: La media de ese rival en el sector, para enseñarla junto a la propia.
    best_rival_value: float
    #: Quién sostiene el sector en el once, con la habilidad: «Bordalás (Def 18)».
    who: str
    #: Lo mismo, sin juntar: la pantalla lo compone y la sigla se traduce.
    who_items: list[QuienSostiene]
    tone: str
    verdict: str


@dataclass
class Subida:
    ht_player_id: int
    player: str
    skill: str
    skill_label: str
    from_level: int
    #: Cuánto crece el sector con un nivel más, en % de lo que ya aporta el once.
    gain_pct: float
    impact: str


@dataclass
class HabilidadesResponse:
    skills: list[dict[str, str]]
    players: list[FilaJugador]
    depth: list[Profundidad]
    sectors: list[Sector] = field(default_factory=list)
    bottleneck: str | None = None
    upgrades: list[Subida] = field(default_factory=list)
    last_match_date: str | None = None
    formation: str | None = None
    #: El reparto de la última formación oficial: cuántos jugaron por dentro.
    last_central_defenders: int | None = None
    last_inner_midfielders: int | None = None
    #: La formación con la que se calcula Profundidad: la última o la elegida.
    depth_formation: str | None = None
    depth_central_defenders: int | None = None
    depth_inner_midfielders: int | None = None
    #: Los repartos legales de esa formación, para el selector.
    central_defender_options: list[int] = field(default_factory=list)
    inner_midfielder_options: list[int] = field(default_factory=list)


def _para_el_motor(j: Jugador) -> dict[str, Any]:
    return {"skills": j.skills, **j.motor}


def once_para_formacion(
    jugadores: list[Jugador],
    once_real: list[Jugador],
    formation: str,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> dict[int, str]:
    """El once con el que jugarías OTRA formación (2026-09-14, pedido del
    usuario: poder escoger la formación en Profundidad).

    Primero siguen los titulares reales en su puesto, los mejores si ahora
    sobran plazas. Después las plazas libres se llenan de una en una con el
    jugador sano que más rinde en alguna de ellas. Así cambiar de 3 a 2
    Defensas Centrales deja al tercero en el banquillo, y pasa a contar como
    recambio."""
    plazas = Counter(slots_for(formation, central_defenders, inner_midfielders))
    asignado: dict[int, str] = {}
    for grupo, cuantos in plazas.items():
        reales = sorted(
            (j for j in once_real if j.grupo == grupo and not j.injured),
            key=lambda j: -rate(_para_el_motor(j), grupo).rating,
        )
        for j in reales[:cuantos]:
            asignado[j.ht_player_id] = grupo
    libres = {g: n - sum(1 for x in asignado.values() if x == g) for g, n in plazas.items()}
    sanos = [j for j in jugadores if not j.injured]
    while any(n > 0 for n in libres.values()):
        mejor: tuple[float, Jugador, str] | None = None
        for grupo, n in libres.items():
            if n <= 0:
                continue
            principal = HABILIDAD_DEL_PUESTO[grupo]
            for j in sanos:
                if j.ht_player_id in asignado or j.skills.get(principal, 0) < MINIMO_PARA_EL_PUESTO:
                    continue
                valor = rate(_para_el_motor(j), grupo).rating
                if mejor is None or valor > mejor[0]:
                    mejor = (valor, j, grupo)
        if mejor is None:
            break
        _, elegido, grupo = mejor
        asignado[elegido.ht_player_id] = grupo
        libres[grupo] -= 1
    return asignado


def profundidad(jugadores: list[Jugador], once: dict[int, str]) -> list[Profundidad]:
    """POR PUESTO Y CONTRA EL SUPLENTE REAL (2026-09-14, pedido del usuario).

    Antes se comparaba el mejor de una habilidad con el segundo mejor, y en
    defensa central los dos eran titulares: si se lesiona Bordalás no entra
    Teano, que ya está jugando, sino el mejor que se quedó en el banquillo.
    Con tres defensas centrales en la última formación, ése es el cuarto; con
    dos delanteros, el tercero.

    - Los puestos y cuántos juegan de cada uno salen del once: el titular del
      último partido oficial o el de la formación que se elija (`once` va de
      identificador de jugador a puesto).
    - El suplente es el mejor jugador sano que NO fue titular, ordenado por el
      rendimiento en ese puesto (el motor de Posiciones), no por una sola
      habilidad: un delantero también necesita Pases.
    - Si el mismo jugador es el recambio de dos puestos se dice, porque no
      puede tapar los dos a la vez, y se nombra quién entraría después.
    - Quien no llega a débil (4) en la habilidad principal del puesto no es
      recambio: con los datos reales salía Bahlek, Portería 1, de recambio de
      portero, porque su Defensa y su forma pesaban más que la Portería 5 de
      un veterano con la forma por los suelos."""
    banquillo = [j for j in jugadores if not j.injured and j.ht_player_id not in once]
    por_grupo = Counter(once.values())

    def candidato(j: Jugador, grupo: str) -> Candidato:
        return Candidato(
            ht_player_id=j.ht_player_id,
            # Nombre completo (2026-09-14, pedido del usuario): «Bahlek» solo
            # no dice tanto como «Klaus Bahlek» en una tabla de recambios.
            name=j.name,
            rating=rate(_para_el_motor(j), grupo).rating,
            skill_level=j.skills.get(HABILIDAD_DEL_PUESTO[grupo], 0),
        )

    salida: list[Profundidad] = []
    for grupo in ORDEN_DE_GRUPOS:
        if not por_grupo.get(grupo):
            continue
        del_puesto = sorted(
            (candidato(j, grupo) for j in jugadores if once.get(j.ht_player_id) == grupo),
            key=lambda c: -c.rating,
        )
        mejor = del_puesto[0]
        principal = HABILIDAD_DEL_PUESTO[grupo]
        opciones = sorted(
            (
                candidato(j, grupo)
                for j in banquillo
                if j.skills.get(principal, 0) >= MINIMO_PARA_EL_PUESTO
            ),
            key=lambda c: -c.rating,
        )
        suplente = opciones[0] if opciones else None
        siguiente = opciones[1] if len(opciones) > 1 else None
        caida = (
            round(max(0.0, 1 - suplente.rating / mejor.rating) * 100, 1)
            if suplente and mejor.rating
            else None
        )
        if caida is None or caida >= 30:
            tone = "danger"
        elif caida >= 15:
            tone = "warning"
        else:
            tone = "ok"
        salida.append(
            Profundidad(
                key=grupo,
                label=PLURAL[grupo],
                starters=por_grupo[grupo],
                skill_label=NOMBRE[HABILIDAD_DEL_PUESTO[grupo]],
                best=mejor,
                substitute=suplente,
                next_substitute=siguiente,
                drop_pct=caida,
                also_covers=[],
                tone=tone,
            )
        )
    recambio_de: dict[int, list[str]] = defaultdict(list)
    for fila_ in salida:
        if fila_.substitute:
            recambio_de[fila_.substitute.ht_player_id].append(fila_.label)
    for fila_ in salida:
        if fila_.substitute:
            fila_.also_covers = [
                p for p in recambio_de[fila_.substitute.ht_player_id] if p != fila_.label
            ]
    return salida


def _clave_del_motor(j: Jugador) -> str | None:
    grupo = j.grupo
    if grupo is None:
        return None
    return VARIANTE.get((grupo, j.behaviour or 0), grupo)


def sectores(serie: list[SectoresDeEquipo], once: list[Jugador]) -> list[Sector]:
    """Defensa, mediocampo y ataque, cada uno frente a la serie.

    Los tres sectores NO se comparan entre sí: el mediocampo va en otra escala
    que las zonas de defensa y ataque (20 frente a 74-89 en el mismo partido),
    así que ponerlos lado a lado decía que el mediocampo era un cuarto de la
    defensa. Cada uno se sitúa entre el peor y el mejor de la serie, con la
    media de los últimos partidos oficiales de cada equipo --la misma medida
    que la flor del Dashboard--.

    EL CUELLO DE BOTELLA ES EL SECTOR CON MENOS VENTAJA SOBRE EL MEJOR RIVAL.
    Con la posición en la serie, un equipo que lidera los tres sectores salía
    con los tres en 100 y sin cuello de botella, aunque en mediocampo estuviera
    empatado con el segundo (16,8 frente a 16,8) y en defensa le sacara el
    doble. La ventaja sobre el mejor rival sí los distingue, y cuando el equipo
    va por detrás es el sector donde más pierde."""
    propio = next((e for e in serie if e.es_propio), None)
    if propio is None:
        return []
    valores: dict[str, float] = {}
    posiciones: dict[str, float] = {}
    ventajas: dict[str, float] = {}
    rivales: dict[str, str] = {}
    valores_rival: dict[str, float] = {}
    campos = (("defensa", "defensa"), ("mediocampo", "medio"), ("ataque", "ataque"))
    for clave, campo in campos:
        mio = getattr(propio, campo)
        todos = [getattr(e, campo) for e in serie if getattr(e, campo) is not None]
        otros = [e for e in serie if not e.es_propio and getattr(e, campo) is not None]
        if mio is None or not otros:
            return []
        minimo, maximo = min(todos), max(todos)
        valores[clave] = mio
        posiciones[clave] = 50.0 if maximo == minimo else (mio - minimo) / (maximo - minimo) * 100
        mejor_rival = max(otros, key=lambda e: getattr(e, campo))
        su_valor = getattr(mejor_rival, campo)
        ventajas[clave] = (mio / su_valor - 1) * 100 if su_valor else 0.0
        rivales[clave] = mejor_rival.nombre
        valores_rival[clave] = su_valor
    peor = min(ventajas, key=lambda k: ventajas[k])

    def quien_piezas(grupos: dict[str, str]) -> list[QuienSostiene]:
        # Con la habilidad delante del número: «Bordalás 18» no decía 18 de qué.
        filas = sorted(
            ((j, grupos[j.grupo]) for j in once if j.grupo in grupos),
            key=lambda par: -par[0].skills.get(par[1], 0),
        )
        return [
            QuienSostiene(j.short_name, SIGLA_DE_HABILIDAD[s], j.skills.get(s, 0))
            for j, s in filas[:4]
        ]

    def quien(piezas: list[QuienSostiene]) -> str:
        return " · ".join(f"{p.player} ({p.sigla} {p.nivel})" for p in piezas)

    piezas_por_sector = {
        "defensa": quien_piezas({"central_defender": "defending", "wingback": "defending"}),
        "mediocampo": quien_piezas({"inner_midfield": "playmaking", "winger": "playmaking"}),
        "ataque": quien_piezas({"forward": "scoring", "winger": "winger"}),
    }
    salida: list[Sector] = []
    for clave, label in (
        ("defensa", "Defensa"),
        ("mediocampo", "Mediocampo"),
        ("ataque", "Ataque"),
    ):
        ventaja = ventajas[clave]
        if ventaja < 0 and clave == peor:
            tone, verdict = "danger", "Aquí se pierde"
        elif ventaja < 0:
            tone, verdict = "warning", "Por detrás"
        elif ventaja < 5:
            tone, verdict = "warning", "Sin ventaja"
        else:
            tone, verdict = "ok", "Fuerte"
        salida.append(
            Sector(
                key=clave,
                label=label,
                rating=round(valores[clave], 1),
                series_position=round(posiciones[clave], 1),
                margin_pct=round(ventaja, 1),
                best_rival=rivales[clave],
                best_rival_value=round(valores_rival[clave], 1),
                who=quien(piezas_por_sector[clave]),
                who_items=piezas_por_sector[clave],
                tone=tone,
                verdict=verdict,
            )
        )
    return salida


def subidas(once: list[Jugador], sector: str, cuantas: int = 3) -> list[Subida]:
    """Qué nivel de qué jugador del once aporta más a un sector.

    Con la tabla de contribución, un nivel más de una habilidad suma su peso
    en ese puesto (rebajado si hay varios en el mismo puesto). Se expresa como
    % de lo que el once ya aporta al sector, que es lo que se puede comparar."""
    del_motor = SECTORES_DEL_MOTOR[sector]
    por_grupo = Counter(j.grupo for j in once)
    total = 0.0
    candidatos: list[tuple[float, Jugador, str]] = []
    for j in once:
        tabla = POSITION_SECTOR_CONTRIBUTION.get(_clave_del_motor(j) or "")
        if not tabla or j.grupo is None:
            continue
        factor = OVERCROWDING_PENALTY.get(j.grupo, {}).get(por_grupo[j.grupo], 1.0)
        pesos: dict[str, float] = defaultdict(float)
        for s in del_motor:
            for skill, peso in tabla.get(s, {}).items():
                pesos[skill] += peso * factor
        total += sum(j.skills.get(k, 0) * p for k, p in pesos.items())
        candidatos.extend((p, j, k) for k, p in pesos.items())
    if total <= 0 or not candidatos:
        return []
    candidatos.sort(key=lambda c: -c[0])
    mejor = candidatos[0][0]
    return [
        Subida(
            ht_player_id=j.ht_player_id,
            player=j.short_name,
            skill=skill,
            skill_label=NOMBRE[skill],
            from_level=j.skills.get(skill, 0),
            gain_pct=round(peso / total * 100, 1),
            impact="Alto" if peso >= 0.6 * mejor else "Medio",
        )
        for peso, j, skill in candidatos[:cuantas]
    ]


def formacion(once: list[Jugador]) -> str | None:
    grupos = Counter(j.grupo for j in once)
    defensa = grupos["central_defender"] + grupos["wingback"]
    medio = grupos["inner_midfield"] + grupos["winger"]
    ataque = grupos["forward"]
    if defensa + medio + ataque == 0:
        return None
    return f"{defensa}-{medio}-{ataque}"


def fila(j: Jugador) -> FilaJugador:
    grupo = j.grupo
    return FilaJugador(
        ht_player_id=j.ht_player_id,
        name=j.name,
        age=j.age,
        tsi=j.tsi,
        position=SIGLA.get(grupo) if grupo else None,
        position_label=ETIQUETA.get(grupo) if grupo else None,
        position_skill=HABILIDAD_DEL_PUESTO.get(grupo) if grupo else None,
        skills=j.skills,
        specialty=SPECIALTIES.get(j.specialty, "") if j.specialty else "",
        injured=j.injured,
        in_lineup=j.in_lineup,
        country_code=j.country_code,
        native_league_name=j.native_league_name,
    )


def orden_del_mapa(j: Jugador) -> tuple[int, int]:
    grupo = j.grupo
    posicion = ORDEN_DE_GRUPOS.index(grupo) if grupo in ORDEN_DE_GRUPOS else len(ORDEN_DE_GRUPOS)
    return posicion, -j.tsi


class HabilidadesQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        team_id: int,
        formation: str | None = None,
        central_defenders: int | None = None,
        inner_midfielders: int | None = None,
    ) -> HabilidadesResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        ultimo = (
            select(
                m.PlayerSnapshot.player_id.label("pid"),
                func.max(m.PlayerSnapshot.captured_at).label("mx"),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
            .group_by(m.PlayerSnapshot.player_id)
            .subquery()
        )
        filas = (
            await self._s.execute(
                select(m.PlayerSnapshot, m.Player)
                .join(
                    ultimo,
                    (m.PlayerSnapshot.player_id == ultimo.c.pid)
                    & (m.PlayerSnapshot.captured_at == ultimo.c.mx),
                )
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            )
        ).all()

        # El último partido oficial jugado: su alineación es «el once» y sus
        # ratings, la medida del cuello de botella.
        recientes = (
            await self._s.execute(
                select(m.Match)
                .where(
                    or_(
                        m.Match.home_team_ht_id == team.ht_team_id,
                        m.Match.away_team_ht_id == team.ht_team_id,
                    )
                )
                .order_by(m.Match.played_at.desc())
                .limit(40)
            )
        ).scalars()
        partido = next(
            (
                p
                for p in recientes
                if (p.status or "").upper() == "FINISHED"
                and is_competitive_match_type(p.match_type)
            ),
            None,
        )

        # EL ONCE ES EL QUE SALIÓ DE INICIO. La ficha de cada jugador guarda su
        # último partido, pero ahí también está el que entró de cambio: salían
        # 14 y una formación 7-4-2. La alineación enviada trae los once
        # titulares con su puesto y su orden, así que manda ella.
        titulares: dict[int, tuple[int, int]] = {}
        if partido is not None and partido.submitted_lineup_json:
            try:
                for item in json.loads(partido.submitted_lineup_json):
                    rol = int(item.get("role_id") or 0)
                    if rol in GRUPO_DEL_PUESTO:
                        titulares[int(item["ht_player_id"])] = (
                            rol,
                            int(item.get("behaviour") or 0),
                        )
            except (ValueError, TypeError, KeyError):
                titulares = {}

        # El codigo de pais de cada CountryID, igual que en la plantilla.
        codigos_de_pais = {
            int(country_id): str(country_code).upper()
            for country_id, country_code in (
                await self._s.execute(
                    select(m.WorldContext.country_id, m.WorldContext.country_code).where(
                        m.WorldContext.country_code != ""
                    )
                )
            ).all()
        }

        jugadores: list[Jugador] = []
        for snap, jugador in filas:
            titular = titulares.get(jugador.ht_player_id)
            jugo_el_ultimo = partido is not None and snap.last_match_ht_id == partido.ht_match_id
            jugadores.append(
                Jugador(
                    ht_player_id=jugador.ht_player_id,
                    name=f"{jugador.first_name or ''} {jugador.last_name or ''}".strip(),
                    short_name=jugador.last_name or jugador.first_name or "?",
                    age=snap.age_years or 0,
                    tsi=snap.tsi or 0,
                    skills={k: getattr(snap, k) or 0 for k, _, _ in HABILIDADES},
                    specialty=snap.specialty or 0,
                    injured=(snap.injury_level or -1) >= 0,
                    # La alineación dice QUIÉN salió de titular; el puesto y la
                    # orden, la ficha: la alineación enviada puso de interiores
                    # a los dos que jugaron de delanteros (107/109 frente a
                    # 111/113) y salía un 5-5-0.
                    position_code=(
                        snap.last_match_position_code
                        if jugo_el_ultimo or not titular
                        else titular[0]
                    ),
                    behaviour=(
                        snap.last_match_behaviour_code
                        if jugo_el_ultimo or not titular
                        else titular[1]
                    ),
                    in_lineup=titular is not None if titulares else jugo_el_ultimo,
                    country_code=codigos_de_pais.get(snap.country_id),
                    native_league_name=jugador.native_league_name,
                    motor={
                        "form": snap.form,
                        "stamina": snap.stamina,
                        "experience": snap.experience,
                        "loyalty": snap.loyalty,
                        "leadership": snap.leadership,
                        "specialty": snap.specialty,
                    },
                )
            )
        if not titulares:
            # Sin alineación guardada: los once que más minutos jugaron.
            minutos = {
                jugador.ht_player_id: snap.last_match_played_minutes or 0 for snap, jugador in filas
            }
            jugaron = sorted(
                (j for j in jugadores if j.in_lineup),
                key=lambda j: -minutos.get(j.ht_player_id, 0),
            )
            for j in jugaron[11:]:
                j.in_lineup = False
        jugadores.sort(key=orden_del_mapa)
        once = [j for j in jugadores if j.in_lineup and j.grupo is not None]

        # LA FORMACIÓN DE PROFUNDIDAD (2026-09-14, pedido del usuario): la del
        # último partido oficial, o la que se elija con su reparto. El cuello
        # de botella sigue midiendo el once real, que es el que jugó.
        por_puesto = Counter(j.grupo for j in once)
        ultima = formacion(once)
        ultima_centrales = por_puesto["central_defender"] if once else None
        ultima_medios = por_puesto["inner_midfield"] if once else None
        if formation in LINE_COUNTS and once:
            centrales, medios = resolve_split(formation, central_defenders, inner_midfielders)
            once_profundidad = once_para_formacion(jugadores, once, formation, centrales, medios)
            formacion_profundidad: str | None = formation
        else:
            once_profundidad = {j.ht_player_id: j.grupo for j in once if j.grupo}
            formacion_profundidad = ultima
            centrales, medios = ultima_centrales, ultima_medios  # type: ignore[assignment]
        catalogada = formacion_profundidad in LINE_COUNTS

        los_sectores = sectores(await sectores_de_la_serie(self._s, team), once) if once else []
        peor = min(los_sectores, key=lambda s: s.margin_pct) if los_sectores else None
        return HabilidadesResponse(
            skills=[{"key": k, "label": n, "short": s} for k, n, s in HABILIDADES],
            players=[fila(j) for j in jugadores],
            depth=profundidad(jugadores, once_profundidad),
            sectors=los_sectores,
            bottleneck=peor.label if peor else None,
            upgrades=subidas(once, peor.key) if peor else [],
            last_match_date=partido.played_at.date().isoformat() if partido and once else None,
            formation=ultima,
            last_central_defenders=ultima_centrales,
            last_inner_midfielders=ultima_medios,
            depth_formation=formacion_profundidad,
            depth_central_defenders=centrales,
            depth_inner_midfielders=medios,
            central_defender_options=(
                central_defender_options(formacion_profundidad or "") if catalogada else []
            ),
            inner_midfielder_options=(
                inner_midfielder_options(formacion_profundidad or "") if catalogada else []
            ),
        )
