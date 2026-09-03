"""Structured comparison for the Changes screen.

Hattrick Control's useful idea is not the notification text itself.  It keeps
the last meaningful comparison visible and aggregates positive, negative and
net movement.  This query builds that report from our append-only snapshots;
no value is inferred from presentation strings and no synthetic data is used.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import start_of_iso_week
from app.domain.engines import academy_engine as academy
from app.domain.engines.sync_diff import Change, diff_training
from app.domain.value_objects.formatting import thousands
from app.domain.value_objects.ht_constants import (
    CONFIDENCE,
    TEAM_SPIRIT,
    TRAINING_TYPES,
)
from app.infrastructure.db import models as m

PLAYER_METRICS: tuple[tuple[str, str, str], ...] = (
    ("tsi", "TSI", "TSI"),
    ("salary", "Salario", "SAL"),
    ("form", "Forma", "FO"),
    ("stamina", "Resistencia", "CO"),
    ("experience", "Experiencia", "EX"),
    ("loyalty", "Fidelidad", "FI"),
    ("leadership", "Liderazgo", "LI"),
    ("keeper", "Portería", "PO"),
    ("defending", "Defensa", "DE"),
    ("playmaking", "Jugadas", "JU"),
    ("winger", "Lateral", "LA"),
    ("passing", "Pases", "PA"),
    ("scoring", "Anotación", "AN"),
    ("set_pieces", "Balón parado", "BP"),
)

POPULARITY: dict[int, str] = {
    0: "Sanguinarios",
    1: "Furiosos",
    2: "Irritados",
    3: "Tranquilos",
    4: "Contentos",
    5: "Satisfechos",
    6: "Delirantes",
    7: "Eufóricos",
    8: "Bailando en las calles",
    9: "Escribiendo poemas de amor",
}

MEANINGFUL_CATEGORIES = ("jugadores", "entrenamiento", "economía", "economia")


def _iso(sync: m.Sync | None) -> str | None:
    if sync is None:
        return None
    return (sync.finished_at or sync.started_at).isoformat()


def _metric_summary() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "key": key,
            "label": label,
            "abbreviation": abbreviation,
            "upCount": 0,
            "upTotal": 0,
            "downCount": 0,
            "downTotal": 0,
            "net": 0,
        }
        for key, label, abbreviation in PLAYER_METRICS
    }


def _record_delta(summary: dict[str, dict[str, Any]], key: str, delta: int) -> None:
    metric = summary[key]
    metric["net"] += delta
    if delta > 0:
        metric["upCount"] += 1
        metric["upTotal"] += delta
    elif delta < 0:
        metric["downCount"] += 1
        metric["downTotal"] += delta


async def _previous_player_snapshot(
    session: AsyncSession, current: m.PlayerSnapshot
) -> m.PlayerSnapshot | None:
    anterior: m.PlayerSnapshot | None = await session.scalar(
        select(m.PlayerSnapshot)
        .where(
            m.PlayerSnapshot.player_id == current.player_id,
            m.PlayerSnapshot.captured_at < start_of_iso_week(current.captured_at),
        )
        .order_by(m.PlayerSnapshot.captured_at.desc(), m.PlayerSnapshot.id.desc())
        .limit(1)
    )
    return anterior


async def _player_report(
    session: AsyncSession, team_id: int, sync_id: int, currency_rate: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = await session.execute(
        select(m.PlayerSnapshot, m.Player)
        .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        # Sólo la plantilla ACTUAL: las filas de quien se fue se conservan como
        # histórico de traspasos y se marcan con `left_team_at`. Mismo criterio
        # que en `changes_history` — ver el comentario largo de allí.
        .where(
            m.PlayerSnapshot.sync_id == sync_id,
            m.Player.team_id == team_id,
            m.Player.left_team_at.is_(None),
        )
        .order_by(m.Player.last_name, m.Player.first_name)
    )
    summary = _metric_summary()
    rows: list[dict[str, Any]] = []

    for current, player in result.all():
        previous = await _previous_player_snapshot(session, current)
        if previous is None:
            rows.append(
                {
                    "htPlayerId": player.ht_player_id,
                    "name": f"{player.first_name} {player.last_name}".strip(),
                    "tsi": current.tsi,
                    "tsiDelta": None,
                    "salary": int(round(current.salary / currency_rate)),
                    "salaryDelta": None,
                    "isNew": True,
                    "changes": [
                        {
                            "key": "arrival",
                            "label": "Alta en la plantilla",
                            "abbreviation": "ALTA",
                            "before": None,
                            "current": True,
                            "delta": None,
                            "direction": "up",
                        }
                    ],
                }
            )
            continue

        changes: list[dict[str, Any]] = []
        for key, label, abbreviation in PLAYER_METRICS:
            before = getattr(previous, key)
            after = getattr(current, key)
            if before is None or after is None or before == after:
                continue
            if key == "salary":
                before = before / currency_rate
                after = after / currency_rate
            delta = int(round(after)) - int(round(before))
            _record_delta(summary, key, delta)
            if key not in {"tsi", "salary"}:
                changes.append(
                    {
                        "key": key,
                        "label": label,
                        "abbreviation": abbreviation,
                        "before": before,
                        "current": after,
                        "delta": delta,
                        "direction": "up" if delta > 0 else "down",
                    }
                )

        if previous.injury_level != current.injury_level:
            changes.append(
                {
                    "key": "injury",
                    "label": "Lesión",
                    "abbreviation": "LES",
                    "before": previous.injury_level,
                    "current": current.injury_level,
                    "delta": current.injury_level - previous.injury_level,
                    "direction": "up" if current.injury_level < previous.injury_level else "down",
                }
            )

        if previous.is_transfer_listed != current.is_transfer_listed:
            changes.append(
                {
                    "key": "market",
                    "label": "Mercado",
                    "abbreviation": "MER",
                    "before": previous.is_transfer_listed,
                    "current": current.is_transfer_listed,
                    "delta": None,
                    "direction": "neutral",
                }
            )

        tsi_delta = current.tsi - previous.tsi
        current_salary = int(round(current.salary / currency_rate))
        salary_delta = current_salary - int(round(previous.salary / currency_rate))
        if changes or tsi_delta or salary_delta:
            rows.append(
                {
                    "htPlayerId": player.ht_player_id,
                    "name": f"{player.first_name} {player.last_name}".strip(),
                    "tsi": current.tsi,
                    "tsiDelta": tsi_delta,
                    "salary": current_salary,
                    "salaryDelta": salary_delta,
                    "isNew": False,
                    "changes": changes,
                }
            )

    return rows, list(summary.values())


#: Las siete habilidades juveniles, con la misma etiqueta y la misma
#: abreviatura que las de mayores: en Cambios se leen igual, que era la
#: condicion del usuario --«como si fueran habilidades de jugadores»--.
YOUTH_METRICS: tuple[tuple[str, str, str], ...] = tuple(
    (clave, etiqueta, abrev)
    for clave, etiqueta, abrev in PLAYER_METRICS
    if clave in {"keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"}
)


async def _previous_youth_snapshot(
    session: AsyncSession, current: m.YouthSnapshot
) -> m.YouthSnapshot | None:
    """La foto anterior a la SEMANA de esta, igual que en mayores.

    El corte por semana ISO --y no «la foto de antes»-- es lo que evita que
    sincronizar dos veces el mismo dia enseñe un informe vacio y se lleve por
    delante el de verdad.
    """
    anterior: m.YouthSnapshot | None = await session.scalar(
        select(m.YouthSnapshot)
        .where(
            m.YouthSnapshot.youth_player_id == current.youth_player_id,
            m.YouthSnapshot.captured_at < start_of_iso_week(current.captured_at),
        )
        .order_by(m.YouthSnapshot.captured_at.desc(), m.YouthSnapshot.id.desc())
        .limit(1)
    )
    return anterior


def _cambio_juvenil(
    clave: str, etiqueta: str, abrev: str, antes: Any, ahora: Any
) -> dict[str, Any] | None:
    """Un movimiento en UNA habilidad juvenil.

    La particularidad juvenil es que cada habilidad son DOS numeros --lo que
    tiene y hasta donde puede llegar-- y los dos se mueven por separado. Hay
    tres noticias distintas y ninguna puede confundirse con otra:

    - **subio**: el nivel crecio. Es el entrenamiento dando fruto.
    - **revelado**: no se sabia y ahora si. No ha crecido nada; lo que cambio
      es lo que sabemos. Se reconoce porque `before` viene en None.
    - **techo**: se descubrio hasta donde puede llegar.

    Un techo que aparece sin que el nivel se mueva TAMBIEN es noticia, y por
    eso esta funcion devuelve cambios con `delta` en None.
    """
    nivel_antes = getattr(antes, clave)
    nivel_ahora = getattr(ahora, clave)
    techo_antes = getattr(antes, clave + "_max")
    techo_ahora = getattr(ahora, clave + "_max")
    tope_antes = bool(getattr(antes, clave + "_max_reached"))
    tope_ahora = bool(getattr(ahora, clave + "_max_reached"))

    subio = nivel_antes is not None and nivel_ahora is not None and nivel_ahora != nivel_antes
    revelado = nivel_antes is None and nivel_ahora is not None
    techo_nuevo = techo_antes is None and techo_ahora is not None
    techo_movido = (
        techo_antes is not None and techo_ahora is not None and techo_ahora != techo_antes
    )
    tope_nuevo = tope_ahora and not tope_antes
    if not (subio or revelado or techo_nuevo or techo_movido or tope_nuevo):
        return None

    delta = (nivel_ahora - nivel_antes) if subio else None
    if delta is not None and delta > 0:
        direccion = "up"
    elif delta is not None and delta < 0:
        direccion = "down"
    else:
        # Descubrir no es mejorar: pintarlo de verde diria que el chico
        # progreso, cuando lo unico que cambio es que ahora lo vemos.
        direccion = "neutral"

    return {
        "key": clave,
        "label": etiqueta,
        "abbreviation": abrev,
        "before": nivel_antes,
        "current": nivel_ahora,
        "delta": delta,
        "direction": direccion,
        # El techo, que en juveniles es la mitad de la noticia.
        "max": techo_ahora,
        "maxBefore": techo_antes,
        # Recien revelado: deja distinguir «ya sabemos hasta donde llega» de
        # «ha subido».
        "maxIsNew": techo_nuevo,
        "maxReached": tope_ahora,
        "maxJustReached": tope_nuevo,
        # Sin nivel antes: se revelo, no crecio.
        "isReveal": revelado,
    }


def _veredicto_de(foto: Any) -> str | None:
    """La categoria del canterano segun esa foto: crack, promesa, aceptable...

    Sale del mejor techo REVELADO, igual que en la pantalla de Juveniles, para
    que las dos no puedan discrepar sobre el mismo chico.
    """
    techos = [getattr(foto, f"{clave}_max") for clave, _, _ in YOUTH_METRICS]
    conocidos = [t for t in techos if t is not None]
    if not conocidos:
        return None
    return str(academy.categoria_de(max(conocidos)))


def _cuantos_techos(foto: Any) -> int:
    """Cuantas de las siete tienen ya techo revelado en esa foto."""
    return sum(1 for clave, _, _ in YOUTH_METRICS if getattr(foto, f"{clave}_max") is not None)


async def _youth_report(
    session: AsyncSession, team_id: int, sync_id: int, desde: datetime | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Que se movio en la academia, y QUE SIGNIFICA.

    Vive aparte de `_player_report` porque un canterano no tiene TSI ni
    salario, y en cambio cada habilidad suya son dos numeros. Meter los dos
    casos en una sola funcion obligaba a llenar de nulos media fila.

    2026-08-30, pedido por el usuario: enseñar el descubrimiento «de manera mas
    profunda». Una lista de «Pases: techo 3» no dice nada por si sola; lo que
    importa es lo que ese numero CAMBIO:

      * si movio el veredicto del chico --de «fontanero» a «promesa» es una
        noticia, de «fontanero» a «fontanero» es ruido--;
      * y cuanta niebla se levanto en la academia entera, que es el numero que
        dice si merece la pena seguir entrenando «Individual».

    Devuelve `(filas, resumen)`.
    """
    filas: list[dict[str, Any]] = []
    revelaciones = 0
    techos_antes = techos_ahora = 0
    cambios_de_veredicto: list[dict[str, Any]] = []
    resultado = await session.execute(
        select(m.YouthSnapshot, m.YouthPlayer)
        .join(m.YouthPlayer, m.YouthPlayer.id == m.YouthSnapshot.youth_player_id)
        .where(
            m.YouthSnapshot.sync_id == sync_id,
            m.YouthPlayer.team_id == team_id,
            m.YouthPlayer.left_at.is_(None),
        )
        .order_by(m.YouthPlayer.last_name, m.YouthPlayer.first_name)
    )

    filas_academia = resultado.all()
    for actual, juvenil in filas_academia:
        nombre = (juvenil.first_name + " " + juvenil.last_name).strip()
        edad = f"{actual.age_years};{actual.age_days:03d}"
        anterior = await _previous_youth_snapshot(session, actual)
        if anterior is None:
            filas.append(
                {
                    "htYouthPlayerId": juvenil.ht_youth_player_id,
                    "name": nombre,
                    "age": edad,
                    "isNew": True,
                    "changes": [
                        {
                            "key": "arrival",
                            "label": "Llegó a la academia",
                            "abbreviation": "ALTA",
                            "before": None,
                            "current": True,
                            "delta": None,
                            "direction": "up",
                        }
                    ],
                }
            )
            continue

        cambios = []
        for clave, etiqueta, abrev in YOUTH_METRICS:
            c = _cambio_juvenil(clave, etiqueta, abrev, anterior, actual)
            if c is not None:
                cambios.append(c)
                if c["isReveal"] or c["maxIsNew"]:
                    revelaciones += 1

        # Lo que el descubrimiento CAMBIO. Un techo nuevo que no mueve el
        # veredicto es un dato; uno que lo mueve es una noticia.
        antes_v, ahora_v = _veredicto_de(anterior), _veredicto_de(actual)
        techos_antes += _cuantos_techos(anterior)
        techos_ahora += _cuantos_techos(actual)
        # No es un «ascenso»: es que el veredicto CAMBIO. Pasar de no tener
        # ninguno a «fontanero» no es una buena noticia, y llamarlo ascenso
        # seria mentir con la etiqueta. La pantalla decide el enfasis.
        cambio_veredicto = antes_v != ahora_v and ahora_v is not None
        if cambio_veredicto:
            cambios_de_veredicto.append({"name": nombre, "from": antes_v, "to": ahora_v})

        # Poder ascender es noticia UNA vez: el dia que el contador llega a
        # cero. Repetirlo cada semana lo convierte en ruido.
        if actual.can_be_promoted_in == 0 and (anterior.can_be_promoted_in or 0) > 0:
            cambios.append(
                {
                    "key": "promotable",
                    "label": "Ya puede ascender al primer equipo",
                    "abbreviation": "ASC",
                    "before": anterior.can_be_promoted_in,
                    "current": 0,
                    "delta": None,
                    "direction": "up",
                }
            )

        if cambios:
            filas.append(
                {
                    "htYouthPlayerId": juvenil.ht_youth_player_id,
                    "name": nombre,
                    "age": edad,
                    "isNew": False,
                    "changes": cambios,
                    # El veredicto, y si este sync lo movio. Es lo que separa
                    # «se revelo un numero» de «este chico es otra cosa».
                    "verdict": ahora_v,
                    "verdictBefore": antes_v if cambio_veredicto else None,
                }
            )

    # Quien SALIO de la academia desde el informe anterior. Hasta el
    # 2026-08-30 esto no se decia en ningun sitio: un canterano ascendia o se
    # marchaba y la pantalla de Cambios callaba, que es justo el cambio mas
    # grande que le puede pasar a la cantera en una semana.
    salidas: list[dict[str, Any]] = []
    if desde is not None:
        idos = (
            await session.execute(
                select(m.YouthPlayer).where(
                    m.YouthPlayer.team_id == team_id,
                    m.YouthPlayer.left_at.is_not(None),
                    m.YouthPlayer.left_at >= desde,
                )
            )
        ).scalars()
        salidas = [
            {
                "name": f"{j.first_name} {j.last_name}".strip(),
                "leftAt": j.left_at.isoformat() if j.left_at else None,
            }
            for j in idos
        ]

    # Cuanta niebla queda en la academia entera. Es el numero que dice si
    # todavia merece la pena entrenar «Individual» o si ya se puede construir.
    total_lecturas = len(filas_academia) * len(YOUTH_METRICS)
    resumen = {
        "revelations": revelaciones,
        "ceilingsBefore": techos_antes,
        "ceilingsNow": techos_ahora,
        "readings": total_lecturas,
        "verdictChanges": cambios_de_veredicto,
        "left": salidas,
    }
    return filas, resumen


async def _snapshot_for_sync_or_before(
    session: AsyncSession,
    model: type[m.TrainingSnapshot] | type[m.EconomySnapshot],
    team_id: int,
    sync: m.Sync,
) -> tuple[Any | None, Any | None, bool]:
    #  explicito:  es una de DOS tablas distintas, asi que el
    # analizador solo puede prometer la clase base comun. La funcion ya declara
    # que devuelve ; esto lo dice tambien donde se lee.
    current: Any = await session.scalar(
        select(model)
        .where(model.team_id == team_id, model.sync_id == sync.id)
        .order_by(model.id.desc())
        .limit(1)
    )
    exact = current is not None
    if current is None:
        current = await session.scalar(
            select(model)
            .where(
                model.team_id == team_id, model.captured_at <= (sync.finished_at or sync.started_at)
            )
            .order_by(model.id.desc())
            .limit(1)
        )
    if current is None:
        return None, None, False
    previous = await session.scalar(
        select(model)
        .where(
            model.team_id == team_id,
            model.captured_at < start_of_iso_week(current.captured_at),
        )
        .order_by(model.captured_at.desc(), model.id.desc())
        .limit(1)
    )
    if not exact:
        previous = current
    return current, previous, exact


async def _ultimo_nivel_psicologico(
    session: AsyncSession,
    team_id: int,
    campo: Any,
    limite: m.TrainingSnapshot,
    *,
    incluir_limite: bool = True,
) -> int | None:
    """Último nivel real hasta una foto; -1/NULL no participan.

    La consulta se hace por campo porque durante un partido Hattrick puede
    ocultar uno y publicar el otro. Usar una sola fila para ambos volvería a
    acoplarlos y perdería un cambio válido.
    """
    # La comparación temporal pertenece a captured_at, no a la columna de
    # nivel. Se deja separada para que el operador inclusivo sea explícito.
    comparacion = or_(
        m.TrainingSnapshot.captured_at < limite.captured_at,
        and_(
            m.TrainingSnapshot.captured_at == limite.captured_at,
            (
                m.TrainingSnapshot.id <= limite.id
                if incluir_limite
                else m.TrainingSnapshot.id < limite.id
            ),
        ),
    )
    value = await session.scalar(
        select(campo)
        .where(
            m.TrainingSnapshot.team_id == team_id,
            comparacion,
            campo.is_not(None),
            campo >= 0,
        )
        .order_by(
            m.TrainingSnapshot.captured_at.desc(),
            m.TrainingSnapshot.id.desc(),
        )
        .limit(1)
    )
    return int(value) if value is not None else None


def _club_item(
    key: str,
    label: str,
    before: int | None,
    current: int | None,
    names: dict[int, str] | None = None,
    *,
    good: bool | None = None,
    solo_nombre: bool = False,
    sufijo: str = "",
) -> dict[str, Any]:
    """`solo_nombre` para lo que es una CATEGORÍA y no una cantidad: el tipo de
    entrenamiento se llama "Pases" o "Defensa", y restar 10 menos 2 no
    significa nada. Sin él, la pantalla enseñaría un "-8" sin sentido."""

    def display(value: int | None) -> str | None:
        if value is None:
            return None
        if names is None:
            return f"{thousands(value)}{sufijo}"
        if solo_nombre:
            return names.get(value, f"Tipo {value}")
        return f"{names.get(value, 'Nivel')} ({value})"

    delta = None if before is None or current is None or solo_nombre else current - before
    if good is None or delta is None or delta == 0:
        is_good = None
    else:
        is_good = (delta > 0) if good else (delta < 0)

    return {
        "key": key,
        "label": label,
        "before": before,
        "current": current,
        "beforeDisplay": display(before),
        "currentDisplay": display(current),
        "delta": delta,
        "changed": before is not None and current is not None and before != current,
        "isGood": is_good,
    }


async def _club_report(
    session: AsyncSession, team_id: int, sync: m.Sync, currency_rate: float
) -> list[dict[str, Any]]:
    training, old_training, _ = await _snapshot_for_sync_or_before(
        session, m.TrainingSnapshot, team_id, sync
    )
    economy, old_economy, _ = await _snapshot_for_sync_or_before(
        session, m.EconomySnapshot, team_id, sync
    )
    items: list[dict[str, Any]] = []
    if training is not None:
        current_morale = await _ultimo_nivel_psicologico(
            session,
            team_id,
            m.TrainingSnapshot.morale,
            training,
        )
        current_confidence = await _ultimo_nivel_psicologico(
            session,
            team_id,
            m.TrainingSnapshot.self_confidence,
            training,
        )
        old_morale = (
            await _ultimo_nivel_psicologico(
                session,
                team_id,
                m.TrainingSnapshot.morale,
                old_training,
            )
            if old_training is not None
            else None
        )
        old_confidence = (
            await _ultimo_nivel_psicologico(
                session,
                team_id,
                m.TrainingSnapshot.self_confidence,
                old_training,
            )
            if old_training is not None
            else None
        )
        items.extend(
            (
                _club_item(
                    "team_spirit",
                    "Espíritu del equipo",
                    old_morale,
                    current_morale,
                    TEAM_SPIRIT,
                ),
                _club_item(
                    "self_confidence",
                    "Confianza",
                    old_confidence,
                    current_confidence,
                    CONFIDENCE,
                ),
                # 2026-08-22, reportado por el usuario: cambió el tipo de
                # entrenamiento y no aparecía por ninguna parte. El cambio se
                # guardaba desde siempre, pero esta pantalla solo pintaba
                # ánimo, confianza y economía: el entrenamiento no tenía
                # dónde salir.
                _club_item(
                    "training_type",
                    "Tipo de entrenamiento",
                    old_training.training_type if old_training else None,
                    training.training_type,
                    TRAINING_TYPES,
                    solo_nombre=True,
                ),
                _club_item(
                    "training_level",
                    "Intensidad",
                    old_training.training_level if old_training else None,
                    training.training_level,
                    sufijo="%",
                ),
                _club_item(
                    "stamina_part",
                    "Parte de resistencia",
                    old_training.stamina_part if old_training else None,
                    training.stamina_part,
                    sufijo="%",
                ),
            )
        )
    if economy is not None:

        def conv(value: int | None) -> int | None:
            return None if value is None else int(round(value / currency_rate))

        items.extend(
            (
                _club_item(
                    "cash",
                    "Caja",
                    conv(old_economy.cash if old_economy else None),
                    conv(economy.cash),
                    good=True,
                ),
                _club_item(
                    "income_sum",
                    "Ingresos totales",
                    conv(old_economy.income_sum if old_economy else None),
                    conv(economy.income_sum),
                    good=True,
                ),
                _club_item(
                    "costs_sum",
                    "Gastos totales",
                    conv(old_economy.costs_sum if old_economy else None),
                    conv(economy.costs_sum),
                    good=False,
                ),
                _club_item(
                    "fan_club_size",
                    "Aficionados",
                    old_economy.fan_club_size if old_economy else None,
                    economy.fan_club_size,
                    good=True,
                ),
                _club_item(
                    "supporters_popularity",
                    "Popularidad con la afición",
                    old_economy.supporters_popularity if old_economy else None,
                    economy.supporters_popularity,
                    POPULARITY,
                    good=True,
                ),
            )
        )
    return items


async def _changes_for_sync(session: AsyncSession, sync_id: int | None) -> list[dict[str, Any]]:
    if sync_id is None:
        return []
    rows = list(
        (
            await session.execute(
                select(m.SyncChange)
                .where(m.SyncChange.sync_id == sync_id)
                .order_by(m.SyncChange.id)
            )
        )
        .scalars()
        .all()
    )

    # Las filas antiguas de Entrenamiento se guardaron con `-1` como valor
    # previo porque el repositorio no incluía moral/confianza en
    # `get_last_values`. Se reconstruyen desde los snapshots inmediatos para
    # que el histórico ya almacenado también sea correcto, sin reescribirlo.
    current_training = await session.scalar(
        select(m.TrainingSnapshot)
        .where(m.TrainingSnapshot.sync_id == sync_id)
        .order_by(m.TrainingSnapshot.id.desc())
        .limit(1)
    )
    # `diff_training` devuelve `list[Change]`, no textos: la anotacion
    # estaba mal y por eso `c.category` parecia un atributo de `str`.
    rebuilt_training: list[Change] | None = None
    if current_training is not None:
        previous_training = await session.scalar(
            select(m.TrainingSnapshot)
            .where(
                m.TrainingSnapshot.team_id == current_training.team_id,
                or_(
                    m.TrainingSnapshot.captured_at < current_training.captured_at,
                    and_(
                        m.TrainingSnapshot.captured_at == current_training.captured_at,
                        m.TrainingSnapshot.id < current_training.id,
                    ),
                ),
            )
            .order_by(m.TrainingSnapshot.captured_at.desc(), m.TrainingSnapshot.id.desc())
            .limit(1)
        )

        def values(snapshot: m.TrainingSnapshot) -> dict[str, Any]:
            return {
                "training_type": snapshot.training_type,
                "training_level": snapshot.training_level,
                "trainer_name": snapshot.trainer_name,
                "morale": snapshot.morale,
                "self_confidence": snapshot.self_confidence,
            }

        current_values = values(current_training)
        current_values["morale"] = await _ultimo_nivel_psicologico(
            session,
            current_training.team_id,
            m.TrainingSnapshot.morale,
            current_training,
        )
        current_values["self_confidence"] = await _ultimo_nivel_psicologico(
            session,
            current_training.team_id,
            m.TrainingSnapshot.self_confidence,
            current_training,
        )
        previous_values = values(previous_training) if previous_training is not None else None
        if previous_values is not None:
            previous_values["morale"] = await _ultimo_nivel_psicologico(
                session,
                current_training.team_id,
                m.TrainingSnapshot.morale,
                current_training,
                incluir_limite=False,
            )
            previous_values["self_confidence"] = await _ultimo_nivel_psicologico(
                session,
                current_training.team_id,
                m.TrainingSnapshot.self_confidence,
                current_training,
                incluir_limite=False,
            )

        rebuilt_training = diff_training(previous_values, current_values)

    def _rebuilt_rows() -> list[dict[str, Any]]:
        return [
            {"category": c.category, "summary": c.summary, "detail": c.detail()}
            for c in (rebuilt_training or [])
        ]

    changes: list[dict[str, Any]] = []
    training_inserted = False
    for row in rows:
        if row.category == "entrenamiento" and rebuilt_training is not None:
            if not training_inserted:
                changes.extend(_rebuilt_rows())
                training_inserted = True
            continue
        changes.append(
            {
                "category": row.category,
                "summary": row.summary,
                # `None` en filas anteriores a 2026-08-15: el frontend cae a su
                # parser de compatibilidad para esas, ver SyncChangesFeed.tsx.
                "detail": json.loads(row.detail_json) if row.detail_json else None,
            }
        )
    if rebuilt_training and not training_inserted:
        changes.extend(_rebuilt_rows())
    return changes


async def build_sync_comparison(
    session: AsyncSession, team_id: int, sync_id: int | None = None
) -> dict[str, Any]:
    """Return the latest sync plus the most recent meaningful comparison.

    Detail syncs (one row per player/match) must not hide the full team sync.
    An empty repeated sync also must not erase the last useful comparison: the
    UI reports both timestamps and says explicitly when the report is older.
    """

    team = await session.get(m.Team, team_id)
    currency_rate = (team.currency_rate or 1.0) if team else 1.0

    normal_sync_filter: Iterable[Any] = (
        m.Sync.team_id == team_id,
        m.Sync.kind.contains("players"),
    )
    latest = await session.scalar(
        select(m.Sync).where(*normal_sync_filter).order_by(m.Sync.started_at.desc()).limit(1)
    )
    if latest is None:
        return {
            "syncId": None,
            "syncedAt": None,
            "changes": [],
            "reportSyncId": None,
            "reportSyncedAt": None,
            "reportIsLatest": True,
            "reportChanges": [],
            "playerRows": [],
            "summary": list(_metric_summary().values()),
            "clubChanges": [],
            "nationalMatches": [],
            "availableReports": [],
        }

    meaningful_ids = (
        select(m.SyncChange.sync_id)
        .where(
            m.SyncChange.team_id == team_id,
            m.SyncChange.category.in_(MEANINGFUL_CATEGORIES),
        )
        .distinct()
    )

    # Lista de fechas navegables — pedido explícito 2026-08-15: "que yo solo
    # deba seleccionar una fecha diferente". Sólo entran los syncs que SÍ
    # movieron algo: un sync repetido que confirmó que todo seguía igual no
    # merece una entrada en el selector, sería ruido.
    available = list(
        (
            await session.execute(
                select(m.Sync)
                .where(*normal_sync_filter, m.Sync.id.in_(meaningful_ids))
                .order_by(m.Sync.started_at.desc())
            )
        )
        .scalars()
        .all()
    )
    # `.tuples()` y no `.all()` a secas: una `Row` se comporta como tupla pero
    # no lo es, y construir un dict con ella funciona por casualidad, no por
    # contrato.
    change_counts: dict[int, int] = dict(
        (
            await session.execute(
                select(m.SyncChange.sync_id, func.count(m.SyncChange.id))
                .where(
                    m.SyncChange.team_id == team_id,
                    m.SyncChange.category.in_(MEANINGFUL_CATEGORIES),
                )
                .group_by(m.SyncChange.sync_id)
            )
        )
        .tuples()
        .all()
    )

    # `sync_id` explícito = el usuario eligió una fecha. Se valida contra la
    # lista navegable en vez de confiar en el parámetro: pedir un sync de otro
    # equipo, o uno sin cambios, cae al comportamiento por defecto.
    report_sync = None
    if sync_id is not None:
        report_sync = next((s for s in available if s.id == sync_id), None)
    if report_sync is None:
        # El informe por defecto es el del ULTIMO sync, tenga cambios o no.
        #
        # 2026-08-24, pedido asi: "la vida de las notificaciones es UNICA, lo
        # que fue, fue". Antes, un sync que no movia nada caia al anterior que
        # si movio algo, y sincronizar dos veces seguidas te reenseñaba lo que
        # acababas de leer. El archivo sigue navegable por `sync_id`: lo que
        # se quita es que vuelva SOLO.
        report_sync = latest

    latest_changes = await _changes_for_sync(session, latest.id)
    report_changes = await _changes_for_sync(session, report_sync.id)
    player_rows, summary = await _player_report(session, team_id, report_sync.id, currency_rate)
    club_changes = await _club_report(session, team_id, report_sync, currency_rate)
    # El sync anterior a este, haya movido algo o no: si se tomara el anterior
    # CON cambios, los partidos de seleccion de la ventana intermedia se
    # volverian a anunciar en cada sync vacio.
    anterior = await session.scalar(
        select(m.Sync)
        .where(*normal_sync_filter, m.Sync.started_at < report_sync.started_at)
        .order_by(m.Sync.started_at.desc())
        .limit(1)
    )
    youth_rows, youth_summary = await _youth_report(
        session, team_id, report_sync.id, anterior.started_at if anterior else None
    )
    national_matches = await _partidos_de_seleccion(
        session,
        team_id,
        desde=anterior.started_at if anterior else None,
        hasta=report_sync.started_at,
    )

    return {
        "syncId": latest.id,
        "syncedAt": _iso(latest),
        "changes": latest_changes,
        "reportSyncId": report_sync.id,
        "reportSyncedAt": _iso(report_sync),
        "reportIsLatest": report_sync.id == latest.id,
        "reportChanges": report_changes,
        "playerRows": player_rows,
        # La academia. Va aparte de `playerRows` porque un canterano no
        # tiene TSI ni salario, y en cambio cada habilidad suya son dos
        # numeros: lo que tiene y hasta donde puede llegar.
        "youthRows": youth_rows,
        # Lo que el descubrimiento significa para la academia entera.
        "youthSummary": youth_summary,
        "summary": summary,
        "clubChanges": club_changes,
        "nationalMatches": national_matches,
        "availableReports": [
            {
                "syncId": s.id,
                "syncedAt": _iso(s),
                "changeCount": change_counts.get(s.id, 0),
            }
            for s in available
        ],
    }


#: Los tres codigos que son "jugo con su seleccion": competitiva con reglas
#: normales, con reglas de copa, y amistoso.
TIPOS_DE_SELECCION = (10, 11, 12)


async def _partidos_de_seleccion(
    session: AsyncSession,
    team_id: int,
    desde: datetime | None,
    hasta: datetime,
) -> list[dict[str, Any]]:
    """ "Fulano jugo 62 minutos con su seleccion" — para el informe de Cambios.

    Se sitian por `Match.played_at`, no por cuando los vimos: un partido del
    martes tiene que salir en el informe del martes aunque lo hayamos
    descubierto el jueves.
    """
    filtros = [
        m.Player.team_id == team_id,
        m.Match.match_type.in_(TIPOS_DE_SELECCION),
        m.Match.played_at <= hasta,
    ]
    if desde is not None:
        filtros.append(m.Match.played_at > desde)

    filas = (
        await session.execute(
            select(
                m.Player.ht_player_id,
                m.Player.first_name,
                m.Player.last_name,
                m.Match.match_type,
                m.Match.played_at,
                m.Match.home_team_name,
                m.Match.away_team_name,
                m.PlayerMatchRating.played_minutes,
                m.PlayerMatchRating.rating,
            )
            .select_from(m.PlayerMatchRating)
            .join(m.Player, m.Player.id == m.PlayerMatchRating.player_id)
            .join(m.Match, m.Match.ht_match_id == m.PlayerMatchRating.ht_match_id)
            .where(*filtros)
            .order_by(m.Match.played_at.desc())
        )
    ).all()

    return [
        {
            "htPlayerId": f.ht_player_id,
            "name": f"{f.first_name} {f.last_name}".strip(),
            "minutes": f.played_minutes,
            "rating": f.rating,
            "playedAt": f.played_at.isoformat() if f.played_at else None,
            "competition": (
                "Amistoso de selección" if f.match_type == 12 else "Partido de selección"
            ),
            "match": f"{f.home_team_name} - {f.away_team_name}".strip(" -"),
        }
        for f in filas
    ]
