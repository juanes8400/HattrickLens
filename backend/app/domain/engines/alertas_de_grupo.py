"""Alertas de subidas y bajadas de habilidades dentro de los grupos.

2026-11-18, definidas por el usuario una a una para cerrar la etapa de
desarrollo. Son noticia de UNA sincronización, como Cambios: comparan lo que
llegó en la última con lo que había antes, y con la siguiente se renuevan.

Reglas suyas que aquí se aplican tal cual:

* «Habilidad que pesa» = las que aportan en su mejor puesto según la matriz
  de puestos del Manual no Escrito (la misma de Alineación).
* «Estancada» = pasó la semana en que la previsión de Entrenamiento (fórmula
  del Manual no Escrito) decía que subiría, y no subió.
* «El grupo cae» = la media de una habilidad baja 3 semanas seguidas, con la
  misma gente dentro (si cambia quién entra, ese salto no es bajada).

Funciones puras: reciben lo ya leído y devuelven `Insight`. Ningún umbral
sale de ajustar datos del usuario.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.engines.insights import Insight, Severity
from app.domain.value_objects.ht_constants import SKILL_LABELS

#: Semanas seguidas bajando para «El grupo cae» (dicho por el usuario).
SEMANAS_DEL_GRUPO_QUE_CAE = 3
#: Bajadas en una sola sincronización para «Declive acelerado».
BAJADAS_DEL_DECLIVE_ACELERADO = 2
#: El corte de «Pieza de rotación», el mismo del motor de Etapa.
PERCENTIL_DE_ROTACION = 40


@dataclass(frozen=True)
class JugadorDelSync:
    ht_player_id: int
    name: str
    titularidad: str
    rentabilidad: str
    etapa: str
    #: Su mejor puesto, para comparar suplentes con titulares.
    puesto: str
    #: Las habilidades que aportan en ese puesto.
    pesan: frozenset[str]
    hoy: dict[str, int]
    #: Lo que tenía antes de la última sincronización; None si no cambió nada.
    antes: dict[str, int] | None
    #: Bajadas desde el primer snapshot, las mismas de la Etapa.
    bajadas_totales: int = 0
    #: Su grupo en cada clasificación propia: id de clasificación → id de grupo.
    grupos_propios: dict[int, int] = field(default_factory=dict)

    def subieron(self) -> list[str]:
        if self.antes is None:
            return []
        return [s for s in SKILL_LABELS if self.hoy.get(s, 0) > self.antes.get(s, 0)]

    def bajaron(self) -> list[str]:
        if self.antes is None:
            return []
        return [s for s in SKILL_LABELS if self.hoy.get(s, 0) < self.antes.get(s, 0)]


def _nombres(habilidades: Sequence[str]) -> str:
    return ", ".join(SKILL_LABELS[s] for s in habilidades)


def titular_con_bajada(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A1: un Titular baja una habilidad que pesa en su puesto."""
    out = []
    for j in jugadores:
        pesadas = [s for s in j.bajaron() if s in j.pesan]
        if j.titularidad == "titular" and pesadas:
            out.append(
                Insight(
                    key=f"group.starter_drop.{j.ht_player_id}",
                    severity=Severity.WARNING,
                    title=f"{j.name}, titular, bajó {_nombres(pesadas)}",
                    detail="Es una habilidad que pesa en su puesto en el once.",
                    action="Mira en Alineación si sigue siendo el mejor para ese puesto.",
                    module="alineación",
                    evidence={"ht_player_id": j.ht_player_id, "skills": pesadas},
                )
            )
    return out


def la_bajada_le_saca_del_once(
    jugadores: Sequence[JugadorDelSync], de_titular_a_suplencia: set[int]
) -> list[Insight]:
    """A2: con una bajada esta sincronización, pasó de Titular a Suplencia."""
    out = []
    for j in jugadores:
        if j.ht_player_id in de_titular_a_suplencia and j.bajaron():
            out.append(
                Insight(
                    key=f"group.dropped_from_xi.{j.ht_player_id}",
                    severity=Severity.DANGER,
                    title=f"{j.name} sale del mejor once tras bajar {_nombres(j.bajaron())}",
                    detail="Pasó de Titular a Suplencia en esta sincronización.",
                    action="Revisa la alineación del próximo partido.",
                    module="alineación",
                    evidence={"ht_player_id": j.ht_player_id},
                )
            )
    return out


def suplente_que_empuja(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A3: un Suplencia sube y supera a un Titular de su puesto en esa habilidad."""
    titulares = [j for j in jugadores if j.titularidad == "titular"]
    out = []
    for j in jugadores:
        if j.titularidad != "suplencia" or j.antes is None:
            continue
        for s in j.subieron():
            if s not in j.pesan:
                continue
            superados = [
                t
                for t in titulares
                if t.puesto == j.puesto and j.antes.get(s, 0) <= t.hoy.get(s, 0) < j.hoy.get(s, 0)
            ]
            if superados:
                out.append(
                    Insight(
                        key=f"group.sub_pushing.{j.ht_player_id}",
                        severity=Severity.OPPORTUNITY,
                        title=f"{j.name} ya supera a {superados[0].name} en {SKILL_LABELS[s]}",
                        detail="Es suplente y juegan el mismo puesto.",
                        action="Valora darle el puesto en Alineación.",
                        module="alineación",
                        evidence={"ht_player_id": j.ht_player_id, "skill": s},
                    )
                )
                break
    return out


def reserva_que_despierta(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A4: un Reserva sube una habilidad que pesa en su puesto."""
    return [
        Insight(
            key=f"group.reserve_rising.{j.ht_player_id}",
            severity=Severity.OPPORTUNITY,
            title=f"{j.name}, en reserva, subió {_nombres(pesadas)}",
            detail="Es una habilidad que pesa en su mejor puesto.",
            action="Míralo en Clasificación de jugadores: puede estar cerca de la suplencia.",
            module="clasificación",
            evidence={"ht_player_id": j.ht_player_id, "skills": pesadas},
        )
        for j in jugadores
        if j.titularidad == "reserva" and (pesadas := [s for s in j.subieron() if s in j.pesan])
    ]


@dataclass(frozen=True)
class Atraso:
    """Un jugador que debía haber subido la habilidad entrenada y no subió."""

    ht_player_id: int
    name: str
    titularidad: str
    etapa: str
    skill: str
    semanas_desde_la_subida: int
    semanas_previstas: float


def promesa_estancada(atrasos: Sequence[Atraso]) -> list[Insight]:
    """A5: una Promesa pasó su semana prevista de subida sin subir."""
    return [
        Insight(
            key=f"group.prospect_stalled.{a.ht_player_id}",
            severity=Severity.WARNING,
            title=f"{a.name} no sube {SKILL_LABELS[a.skill]} cuando tocaba",
            detail=(
                f"Lleva {a.semanas_desde_la_subida} semanas desde su última subida y la "
                f"previsión de Entrenamiento era de {a.semanas_previstas:.0f}."
            ),
            action=(
                "Comprueba en Entrenamiento que juega en un puesto que recibe ese entrenamiento."
            ),
            module="entrenamiento",
            evidence={"ht_player_id": a.ht_player_id, "skill": a.skill},
        )
        for a in atrasos
        if a.etapa == "promesa"
    ]


def promesa_que_sube(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A6: una Promesa sube de nivel."""
    return [
        Insight(
            key=f"group.prospect_rose.{j.ht_player_id}",
            severity=Severity.INFO,
            title=f"{j.name}, promesa, subió {_nombres(j.subieron())}",
            detail="Su formación avanza.",
            module="entrenamiento",
            evidence={"ht_player_id": j.ht_player_id},
        )
        for j in jugadores
        if j.etapa == "promesa" and j.subieron()
    ]


def rotacion_que_asoma(
    jugadores: Sequence[JugadorDelSync], de_rotacion_a_pico: set[int]
) -> list[Insight]:
    """A7: una Pieza de rotación sube y supera el percentil 40."""
    return [
        Insight(
            key=f"group.rotation_rising.{j.ht_player_id}",
            severity=Severity.OPPORTUNITY,
            title=f"{j.name} deja de ser pieza de rotación",
            detail=(
                f"Subió {_nombres(j.subieron())} y su habilidad dominante ya pasa el "
                f"percentil {PERCENTIL_DE_ROTACION} de la plantilla: ahora está en su pico."
            ),
            module="clasificación",
            evidence={"ht_player_id": j.ht_player_id},
        )
        for j in jugadores
        if j.ht_player_id in de_rotacion_a_pico and j.subieron()
    ]


def primer_aviso_de_declive(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A8: un Veterano estable tiene su primera bajada."""
    return [
        Insight(
            key=f"group.veteran_first_drop.{j.ht_player_id}",
            severity=Severity.WARNING,
            title=f"Primera bajada de {j.name}: {_nombres(j.bajaron())}",
            detail="Es veterano y hasta ahora no había bajado ninguna habilidad.",
            action="Si sigue bajando, pasará a En declive.",
            module="clasificación",
            evidence={"ht_player_id": j.ht_player_id},
        )
        for j in jugadores
        if j.etapa == "veterano" and j.bajaron() and j.bajadas_totales <= len(j.bajaron())
    ]


def declive_acelerado(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A9: alguien En declive baja 2 o más habilidades en una sincronización."""
    return [
        Insight(
            key=f"group.decline_fast.{j.ht_player_id}",
            severity=Severity.DANGER,
            title=f"{j.name} bajó {len(j.bajaron())} habilidades de una vez",
            detail=f"Está en declive y bajó {_nombres(j.bajaron())}.",
            action="Valora su venta en Transferencias antes de que pierda más valor.",
            module="transferencias",
            evidence={"ht_player_id": j.ht_player_id},
        )
        for j in jugadores
        if j.etapa == "declive" and len(j.bajaron()) >= BAJADAS_DEL_DECLIVE_ACELERADO
    ]


def estrella_que_cae(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A10: una Estrella baja una habilidad que pesa en su puesto."""
    return [
        Insight(
            key=f"group.star_drop.{j.ht_player_id}",
            severity=Severity.WARNING,
            title=f"{j.name}, una de tus estrellas, bajó {_nombres(pesadas)}",
            detail="Cobra por encima de la mediana y la habilidad pesa en su puesto.",
            module="clasificación",
            evidence={"ht_player_id": j.ht_player_id, "skills": pesadas},
        )
        for j in jugadores
        if j.rentabilidad == "estrellas" and (pesadas := [s for s in j.bajaron() if s in j.pesan])
    ]


def caro_que_sigue_bajando(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A11: un Caro baja otra vez."""
    return [
        Insight(
            key=f"group.costly_dropping.{j.ht_player_id}",
            severity=Severity.WARNING,
            title=f"{j.name} vuelve a bajar: {_nombres(j.bajaron())}",
            detail=(
                f"Es de los caros: cobra por encima de la mediana y su futuro está por "
                f"debajo. Lleva {j.bajadas_totales} bajadas desde que hay datos."
            ),
            action="Simula su venta en Transferencias → Plantilla actual.",
            module="transferencias",
            evidence={"ht_player_id": j.ht_player_id},
        )
        for j in jugadores
        if j.rentabilidad == "caros" and j.bajaron() and j.bajadas_totales > len(j.bajaron())
    ]


def ganga_que_se_revaloriza(jugadores: Sequence[JugadorDelSync]) -> list[Insight]:
    """A12: una Ganga sube."""
    return [
        Insight(
            key=f"group.bargain_rising.{j.ht_player_id}",
            severity=Severity.OPPORTUNITY,
            title=f"{j.name}, una ganga, subió {_nombres(j.subieron())}",
            detail="Cobra por debajo de la mediana y vale cada vez más.",
            module="clasificación",
            evidence={"ht_player_id": j.ht_player_id},
        )
        for j in jugadores
        if j.rentabilidad == "gangas" and j.subieron()
    ]


@dataclass(frozen=True)
class SerieDeGrupo:
    """La media semanal de una habilidad en un grupo, con cuántos entran."""

    grupo: str
    clave_del_grupo: str
    skill: str
    valores: Sequence[float | None]
    conteos: Sequence[int]


def el_grupo_cae(series: Sequence[SerieDeGrupo]) -> list[Insight]:
    """A13: la media baja 3 semanas seguidas con la misma gente dentro."""
    n = SEMANAS_DEL_GRUPO_QUE_CAE + 1
    out = []
    for s in series:
        crudos, conteos = list(s.valores)[-n:], list(s.conteos)[-n:]
        valores = [float(v) for v in crudos if v is not None]
        if len(valores) < n:
            continue
        if len(set(conteos)) != 1 or conteos[0] == 0:
            continue
        if all(b < a for a, b in zip(valores, valores[1:], strict=False)):
            out.append(
                Insight(
                    key=f"group.falling_trend.{s.clave_del_grupo}.{s.skill}",
                    severity=Severity.WARNING,
                    title=(
                        f"{s.grupo}: {SKILL_LABELS[s.skill]} baja "
                        f"{SEMANAS_DEL_GRUPO_QUE_CAE} semanas seguidas"
                    ),
                    detail=(
                        f"La media pasó de {valores[0]:.1f} a {valores[-1]:.1f}, con los mismos "
                        f"{conteos[0]} jugadores dentro."
                    ),
                    action="Míralo en Habilidades con «Mirar a» ese grupo.",
                    module="habilidades",
                    evidence={"group": s.clave_del_grupo, "skill": s.skill},
                )
            )
    return out


def entrenamiento_que_no_llega_al_once(atrasos: Sequence[Atraso]) -> list[Insight]:
    """A14: Titulares que pasaron su semana prevista sin subir lo entrenado."""
    tarde = [a for a in atrasos if a.titularidad == "titular"]
    if not tarde:
        return []
    nombres = ", ".join(a.name for a in tarde)
    return [
        Insight(
            key="group.training_not_reaching_xi",
            severity=Severity.WARNING,
            title=f"{len(tarde)} titular(es) no suben {SKILL_LABELS[tarde[0].skill]} cuando tocaba",
            detail=f"Según la previsión de Entrenamiento ya deberían haber subido: {nombres}.",
            action="Comprueba en Entrenamiento quién recibe el entrenamiento por su puesto.",
            module="entrenamiento",
            evidence={"ht_player_ids": [a.ht_player_id for a in tarde]},
        )
    ]


@dataclass(frozen=True)
class GrupoPropio:
    id: int
    nombre: str
    clasificacion_id: int
    clasificacion: str


def tu_grupo_se_movio(
    jugadores: Sequence[JugadorDelSync], grupos: Sequence[GrupoPropio]
) -> list[Insight]:
    """A15: en una clasificación propia, un grupo tuvo subidas o bajadas."""
    out = []
    for g in grupos:
        dentro = [j for j in jugadores if j.grupos_propios.get(g.clasificacion_id) == g.id]
        subidas = sum(len(j.subieron()) for j in dentro)
        bajadas = sum(len(j.bajaron()) for j in dentro)
        if subidas or bajadas:
            out.append(
                Insight(
                    key=f"group.own_moved.{g.id}",
                    severity=Severity.INFO,
                    title=(
                        f"«{g.nombre}» ({g.clasificacion}): {subidas} subida(s) "
                        f"y {bajadas} bajada(s)"
                    ),
                    detail="En la última sincronización, entre los jugadores de tu grupo.",
                    module="clasificación",
                    evidence={"group_id": g.id},
                )
            )
    return out
