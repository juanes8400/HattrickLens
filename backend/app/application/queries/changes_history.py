"""Historical player changes for the Hattrick-Control-style Changes screen.

Unlike the last-sync report, this query walks the append-only player snapshots
and compares weekly closes. It never tries to reconstruct a skill pop from TSI
or presentation text: each before/after pair comes from CHPP values that were
actually saved for the player.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import latest_per_iso_week
from app.infrastructure.db import models as m

# 2026-08-05, pedido explícitamente: "los cambios de la página de cambios
# deben ser efímeros, máximo verse los de la última semana, nada más
# antiguo" — se sigue guardando todo (append-only, la tabla cruda no se
# toca), solo se DEJA DE MOSTRAR lo que ya pasó de una semana.
#
# 2026-08-17: esa sigue siendo la vista POR DEFECTO, pero ahora se puede pedir
# una ventana más ancha a propósito. Son dos preguntas distintas: "¿qué pasó
# esta semana?" —que es la de siempre y quiere ser efímera— y "¿cuánto ha
# crecido este jugador en cuatro meses?", que solo se responde mirando atrás.
# Nada se enseña sin pedirlo: la ventana ancha hay que elegirla.
DEFAULT_WINDOW_WEEKS = 1
ALLOWED_WINDOW_WEEKS: tuple[int, ...] = (1, 2, 4, 8, 16)

# Fidelidad no se persistía al principio: los snapshots del 26-27 de julio de
# 2026 la tienen en 0. Comprobado en la base — `loyalty` y `leadership` valen 0
# exactamente en las mismas 73 filas, y en ninguna posterior. Liderazgo empieza
# en 1 en Hattrick, así que un 0 suyo delata la lectura incompleta; la
# fidelidad sí puede ser 0 de verdad en un fichaje recién llegado, y por eso el
# descarte no puede decidirse por su propio valor.
#
# Sin esto, comparar contra una de esas filas inventa una subida enorme: "0 →
# 20" en Fidelidad para media plantilla, que es un dato que nunca ocurrió. Con
# ventanas de una semana no se notaba porque esas filas ya habían quedado
# fuera; a cuatro semanas vuelven a ser la referencia.
# Liderazgo entra en la lista por el mismo motivo que fidelidad: en esas filas
# vale 0 y ese 0 no es un dato, es la ausencia de uno.
INCOMPLETE_WITHOUT_LEADERSHIP = frozenset({"loyalty", "leadership"})

# 2026-08-17, pedido explícito: el agregado del equipo cubre TODO lo que se
# mide del jugador, no sólo las habilidades — TSI y salario incluidos.
METRICS: tuple[tuple[str, str, str], ...] = (
    ("keeper", "Portería", "skill"),
    ("defending", "Defensa", "skill"),
    ("playmaking", "Jugadas", "skill"),
    ("winger", "Lateral", "skill"),
    ("passing", "Pases", "skill"),
    ("scoring", "Anotación", "skill"),
    ("set_pieces", "Balón parado", "skill"),
    ("stamina", "Condición", "skill"),
    ("experience", "Experiencia", "experience"),
    ("loyalty", "Fidelidad", "loyalty"),
    ("leadership", "Liderazgo", "loyalty"),
    ("form", "Forma", "form"),
    ("tsi", "TSI", "market"),
    ("salary", "Salario", "market"),
)

# El salario llega en la moneda cruda de CHPP y hay que dividirlo por la tasa
# del equipo antes de restar, o el delta sale diez veces más grande.
CURRENCY_METRICS = frozenset({"salary"})


def _name(player: m.Player) -> str:
    return f"{player.first_name} {player.last_name}".strip()


def _naive(value: datetime) -> datetime:
    """SQLite devuelve estos `captured_at` sin tzinfo aunque la columna sea
    aware. Se compara todo en naive para no mezclar los dos tipos."""
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _event(
    current: m.PlayerSnapshot,
    player: m.Player,
    key: str,
    label: str,
    before: int,
    value: int,
) -> dict[str, Any]:
    return {
        "capturedAt": current.captured_at.isoformat(),
        "htPlayerId": player.ht_player_id,
        "name": _name(player),
        "key": key,
        "label": label,
        "before": before,
        "current": value,
        "delta": value - before,
    }


async def build_changes_history(
    session: AsyncSession,
    team_id: int,
    player_ht_id: int | None = None,
    *,
    weeks: int = DEFAULT_WINDOW_WEEKS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Cuánto cambió cada jugador en las últimas `weeks` semanas.

    Es una comparación NETA contra el cierre semanal de hace `weeks` semanas,
    no la lista de cada paso intermedio. A una semana da lo mismo —solo hay un
    paso—, pero a dieciséis la diferencia es todo: un jugador que subió tres
    niveles de Pases sale como una línea que dice 8 → 11, no como tres líneas
    sueltas que hay que sumar de cabeza.
    """
    team = await session.get(m.Team, team_id)
    currency_rate = (team.currency_rate or 1.0) if team else 1.0

    # Sólo la plantilla ACTUAL. Las filas `Player` de quien se fue no se borran
    # nunca —son el histórico de traspasos— y se marcan con `left_team_at`.
    # 2026-08-17, pedido explícito: sin este filtro, Cambios contaba a Viktor
    # Markoč y a media docena de vendidos, y sus cifras entraban además en los
    # balances del equipo. Lo que le pasó a un jugador antes de irse no es un
    # cambio de TU plantilla; para eso está Saldo por jugador.
    rows = (
        await session.execute(
            select(m.PlayerSnapshot, m.Player)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
            .order_by(m.PlayerSnapshot.captured_at, m.PlayerSnapshot.id)
        )
    ).all()

    snapshots: dict[int, list[tuple[m.PlayerSnapshot, m.Player]]] = defaultdict(list)
    for snapshot, player in rows:
        snapshots[player.ht_player_id].append((snapshot, player))

    # La misma regla de las gráficas: un cierre semanal, no un diff por cada
    # vez que se pulsó Sync. Los datos crudos quedan guardados en la tabla.
    snapshots = {
        player_id: latest_per_iso_week(entries, lambda item: item[0].captured_at)
        for player_id, entries in snapshots.items()
    }

    players: list[dict[str, Any]] = [
        {"htPlayerId": ht_player_id, "name": _name(items[-1][1])}
        for ht_player_id, items in snapshots.items()
    ]
    players.sort(key=lambda p: p["name"].casefold())

    latest_player = max(
        snapshots,
        key=lambda ht_player_id: snapshots[ht_player_id][-1][0].captured_at,
        default=None,
    )
    selected_player = player_ht_id if player_ht_id in snapshots else latest_player

    # `captured_at` de SQLite llega naive aunque la columna sea aware (mismo
    # caso que `sold_at` en sync_team.py) — el cutoff se calcula naive para
    # comparar contra el mismo tipo.
    cutoff = ((now or datetime.now(UTC)) - timedelta(weeks=weeks)).replace(tzinfo=None)

    # Contra qué cierre se compara EL EQUIPO: el más reciente que ya existía
    # cuando empezó la ventana. Se calcula sobre todos los cierres juntos, no
    # jugador a jugador, porque es la respuesta a "¿hace cuánto?" que se
    # enseña en pantalla — un fichaje reciente, que abajo se compara contra su
    # propio primer cierre, no puede arrastrar esa fecha hacia atrás y hacer
    # creer que toda la tabla mira cuatro meses atrás.
    closes = sorted({_naive(s.captured_at) for entries in snapshots.values() for s, _ in entries})
    older_closes = [c for c in closes if c <= cutoff]
    compared_from = older_closes[-1] if older_closes else (closes[0] if closes else None)

    grouped: dict[str, list[dict[str, Any]]] = {
        "skill": [],
        "experience": [],
        "loyalty": [],
        "form": [],
        "market": [],
    }
    for entries in snapshots.values():
        current, player = entries[-1]
        # La referencia de cada jugador es su último cierre dentro de los que
        # ya existían al empezar la ventana. Si llegó después no hay contra qué
        # comparar y no se inventa un "antes": se usa su primer cierre, que es
        # lo más viejo que de él se sabe.
        older = [item for item in entries[:-1] if _naive(item[0].captured_at) <= cutoff]
        previous = older[-1][0] if older else (entries[0][0] if len(entries) > 1 else None)
        if previous is None:
            continue
        # ¿La referencia de este jugador es una de las filas viejas a las que
        # les falta media lectura? Ver `INCOMPLETE_WITHOUT_LEADERSHIP`.
        incomplete = not (previous.leadership or 0) > 0
        for key, label, group in METRICS:
            if incomplete and key in INCOMPLETE_WITHOUT_LEADERSHIP:
                continue
            before = getattr(previous, key)
            value = getattr(current, key)
            if before is None or value is None:
                continue
            if key in CURRENCY_METRICS:
                before = round(before / currency_rate)
                value = round(value / currency_rate)
            if before == value:
                continue
            grouped[group].append(_event(current, player, key, label, int(before), int(value)))

    for eventos in grouped.values():
        eventos.sort(key=lambda event: (-abs(event["delta"]), event["name"]))

    series: list[dict[str, Any]] = []
    if selected_player is not None:
        for snapshot, _ in snapshots[selected_player]:
            series.append(
                {
                    "capturedAt": snapshot.captured_at.isoformat(),
                    "tsi": snapshot.tsi,
                    "salary": int(round(snapshot.salary / currency_rate)),
                    "form": snapshot.form,
                    "experience": snapshot.experience,
                    "stamina": snapshot.stamina,
                }
            )

    return {
        "weeks": weeks,
        # Contra qué cierre se está comparando de verdad. Con una ventana de
        # dieciséis semanas y sólo cinco de datos, la respuesta honesta no es
        # "hace dieciséis semanas" sino la fecha del cierre más viejo que hay.
        # Un jugador que llegó después se compara contra su propio primer
        # cierre, que puede ser posterior a éste.
        "comparedFrom": compared_from.isoformat() if compared_from else None,
        "players": players,
        "selectedPlayerId": selected_player,
        "skillChanges": grouped["skill"],
        "experienceChanges": grouped["experience"],
        "loyaltyChanges": grouped["loyalty"],
        "formChanges": grouped["form"],
        "marketChanges": grouped["market"],
        "series": series,
    }
