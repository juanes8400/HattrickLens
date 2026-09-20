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
# antiguo", se sigue guardando todo (append-only, la tabla cruda no se
# toca), solo se DEJA DE MOSTRAR lo que ya pasó de una semana.
#
# 2026-08-17: esa sigue siendo la vista POR DEFECTO, pero ahora se puede pedir
# una ventana más ancha a propósito. Son dos preguntas distintas: "¿qué pasó
# esta semana?", que es la de siempre y quiere ser efímera, y "¿cuánto ha
# crecido este jugador en cuatro meses?", que solo se responde mirando atrás.
# Nada se enseña sin pedirlo: la ventana ancha hay que elegirla.
DEFAULT_WINDOW_WEEKS = 1

#: «Siempre»: contra el PRIMER cierre guardado de cada jugador, sea de cuando
#: sea. Pedido el 2026-09-09 --«vamos a ir al primer dato guardado del
#: jugador»-- y sale barato porque el mecanismo ya existía: un jugador que
#: llegó después del corte ya se comparaba contra su propio primer cierre.
#: Esto no hace más que llevar el corte al principio del tiempo, así que ese
#: camino pasa a valer para todos.
#:
#: Cero y no un número grande de semanas: «16» significa dieciséis semanas y
#: «104» significaría dos años, pero SIEMPRE no es una duración, es la
#: ausencia de corte. Un centinela lo dice; un 9999 lo disimula.
SIEMPRE = 0
ALLOWED_WINDOW_WEEKS: tuple[int, ...] = (SIEMPRE, 1, 2, 4, 8, 16)

# Fidelidad no se persistía al principio: los snapshots del 26-27 de julio de
# 2026 la tienen en 0. Comprobado en la base, `loyalty` y `leadership` valen 0
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
# mide del jugador, no sólo las habilidades, TSI y salario incluidos.
METRICS: tuple[tuple[str, str, str], ...] = (
    ("keeper", "Portería", "skill"),
    ("defending", "Defensa", "skill"),
    ("playmaking", "Jugadas", "skill"),
    ("winger", "Lateral", "skill"),
    ("passing", "Pases", "skill"),
    ("scoring", "Anotación", "skill"),
    ("set_pieces", "Balón parado", "skill"),
    ("stamina", "Resistencia", "skill"),
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


#: Lo que se mide de un CANTERANO en las mismas ventanas que la plantilla.
#:
#: 2026-09-09, pedido del usuario: «que los movimientos de esos jugadores
#: también entren» en «Última semana», «Hace 2 semanas»...
#:
#: Sólo el NIVEL de cada habilidad, que es lo que se mueve. Los techos también
#: cambian --se revelan-- pero eso no es un movimiento sino un descubrimiento:
#: no tiene un «antes» contra el que restar (pasa de desconocido a un número),
#: así que no cabe en una vista de deltas. Los techos siguen contándose enteros
#: en «La cantera», con su veredicto y su niebla, que es donde se entienden.
YOUTH_METRICS: tuple[tuple[str, str], ...] = (
    ("keeper", "Portería"),
    ("defending", "Defensa"),
    ("playmaking", "Jugadas"),
    ("winger", "Lateral"),
    ("passing", "Pases"),
    ("scoring", "Anotación"),
    ("set_pieces", "Balón parado"),
)


def _llegada(
    actual: Any, juvenil: Any, nombre: str, campo: str, etiqueta: str
) -> dict[str, Any]:
    """Una habilidad con la que un canterano ENTRÓ por la puerta.

    Sin «antes» y sin delta: nadie subió ni bajó. Y sin marcarla como
    revelación del ojeador, que es otra cosa y tiene su propia cifra. Hasta el
    2026-09-19 un recién llegado no aparecía en Cambios por ningún lado, y lo
    que es noticia de él es justo con qué llega (pedido del usuario).
    """
    return {
        "capturedAt": actual.captured_at.isoformat(),
        "htPlayerId": juvenil.ht_youth_player_id,
        "name": nombre,
        "isYouth": True,
        "key": campo,
        "label": etiqueta,
        "before": None,
        "current": int(getattr(actual, campo)),
        "delta": None,
        "isReveal": False,
        "isArrival": True,
    }


async def _cambios_de_cantera(
    session: AsyncSession, team_id: int, cutoff: datetime
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Los canteranos, en las mismas ventanas que la plantilla.

    Misma mecánica: un cierre por semana, y la referencia es el último cierre
    anterior al corte (el primero del chico si llegó después). Lo que cambia
    es QUÉ se mide y que aquí hay DOS clases de noticia:

      · MOVIMIENTO. Se sabía y ahora es otro: «Lateral 4 -> 5».
      · DESCUBRIMIENTO. No se sabía y ahora sí: «Pases (techo): 5». Va sin
        `before` y sin `delta`, porque no los tiene: nadie bajó ni subió, se
        levantó la niebla. Pedido el 2026-09-09: «los descubrimientos también
        deben ser reportados como cambios».

    Un juvenil no tiene TSI, ni salario, ni forma, ni experiencia. Lo que sí
    tiene y la plantilla no es un TECHO por habilidad, que es la mitad de la
    información: saber que sus Pases son 3 no dice nada sin saber si se paran
    ahí o llegan a 12.

    Van marcados con `isYouth`. No son intercambiables con los del primer
    equipo --un «Pases +1» de un chico de 17 años no es la misma noticia que
    el de un titular-- y además no se enlazan: su ficha no vive en /players.
    """
    filas = (
        await session.execute(
            select(m.YouthSnapshot, m.YouthPlayer)
            .join(m.YouthPlayer, m.YouthPlayer.id == m.YouthSnapshot.youth_player_id)
            .where(m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None))
            .order_by(m.YouthSnapshot.captured_at, m.YouthSnapshot.id)
        )
    ).all()

    por_juvenil: dict[int, list[tuple[m.YouthSnapshot, m.YouthPlayer]]] = defaultdict(list)
    for snapshot, juvenil in filas:
        por_juvenil[juvenil.ht_youth_player_id].append((snapshot, juvenil))

    eventos: list[dict[str, Any]] = []
    # Las tres cifras del panel, en esta misma ventana. 2026-09-09, pedido del
    # usuario: «estas 3 cifras también deben moverse al son de las ventanas».
    #
    # Ojo con lo que significa cada una, porque no son lo mismo:
    #   · las revelaciones son un FLUJO --cuántas cayeron dentro de la
    #     ventana-- y se recuentan enteras;
    #   · los techos conocidos son un STOCK: cuántos se saben AHORA. Un stock
    #     no cambia según la ventana que se mire, lo que cambia es contra qué
    #     se compara, así que se manda también cuántos se sabían al principio
    #     de la ventana y la pantalla enseña el movimiento.
    techos_ahora = techos_antes = lecturas = 0
    for entries in por_juvenil.values():
        cierres = latest_per_iso_week(entries, lambda item: item[0].captured_at)
        actual, juvenil = cierres[-1]

        # ¿Llegó DENTRO de la ventana? Entonces no hay «antes» contra el que
        # comparar, y hasta hoy eso lo dejaba fuera de Cambios por completo:
        # un chico nuevo no aparecía por ningún lado. Lo que es noticia de él
        # es justo con qué llega (2026-09-19, pedido del usuario).
        #
        # Con la ventana «siempre» no hay recién llegados: el corte está en el
        # principio del tiempo y cada chico se compara contra su propio primer
        # cierre, así que TODOS saldrían como nuevos.
        primero = cierres[0][0]
        llego = cutoff > datetime.min and _naive(primero.captured_at) > cutoff

        nombre = f"{juvenil.first_name} {juvenil.last_name}".strip()

        # Con una sola lectura no hay movimiento que contar: lo único que se
        # puede decir de él es con qué vino.
        if len(cierres) < 2:
            if llego:
                for clave, etiqueta in YOUTH_METRICS:
                    for campo, sufijo in ((clave, ""), (f"{clave}_max", " (techo)")):
                        if getattr(actual, campo) is not None:
                            eventos.append(
                                _llegada(actual, juvenil, nombre, campo, etiqueta + sufijo)
                            )
            continue
        anteriores = [c for c in cierres[:-1] if _naive(c[0].captured_at) <= cutoff]
        previo = anteriores[-1][0] if anteriores else cierres[0][0]
        contados: set[str] = set()
        lecturas += len(YOUTH_METRICS)
        for clave, _etiqueta in YOUTH_METRICS:
            techos_ahora += getattr(actual, f"{clave}_max") is not None
            techos_antes += getattr(previo, f"{clave}_max") is not None
        for clave, etiqueta in YOUTH_METRICS:
            for campo, sufijo in ((clave, ""), (f"{clave}_max", " (techo)")):
                ahora = getattr(actual, campo)
                if ahora is None:
                    continue
                antes = getattr(previo, campo)
                if antes is None:
                    # No se sabía al empezar la ventana. Si además SE MOVIÓ
                    # desde que se supo, manda el movimiento: enseñar sólo
                    # «descubierto: 5» se comería la subida, que es la mitad
                    # de la noticia --lo preguntó el usuario el 2026-09-09,
                    # «¿por qué no aparece Ireneo con Lateral 4 ▲ 5?»--.
                    # Se compara contra el PRIMER valor que se llegó a saber,
                    # nunca contra un desconocido.
                    conocidos = [
                        getattr(c[0], campo)
                        for c in cierres[:-1]
                        if getattr(c[0], campo) is not None
                    ]
                    if conocidos and conocidos[0] != ahora:
                        antes = conocidos[0]
                if antes == ahora:
                    continue
                contados.add(campo)
                eventos.append(
                    {
                        "capturedAt": actual.captured_at.isoformat(),
                        "htPlayerId": juvenil.ht_youth_player_id,
                        "name": nombre,
                        "isYouth": True,
                        "key": campo,
                        "label": etiqueta + sufijo,
                        # `None` es «no se sabía», nunca un cero. Un
                        # descubrimiento viaja sin `before` y sin `delta` en vez
                        # de fingir que subió desde la nada.
                        "before": None if antes is None else int(antes),
                        "current": int(ahora),
                        "delta": None if antes is None else int(ahora) - int(antes),
                        "isReveal": antes is None,
                        "isArrival": llego,
                    }
                )
        if llego:
            for clave, etiqueta in YOUTH_METRICS:
                for campo, sufijo in ((clave, ""), (f"{clave}_max", " (techo)")):
                    if campo in contados or getattr(actual, campo) is None:
                        continue
                    eventos.append(
                        _llegada(actual, juvenil, nombre, campo, etiqueta + sufijo)
                    )
    # Primero lo que más se movió; los descubrimientos, que no tienen tamaño,
    # detrás y por orden alfabético.
    eventos.sort(
        key=lambda e: (e["delta"] is None, -abs(e["delta"] or 0), e["name"], e["key"])
    )
    resumen = {
        "revelations": sum(1 for e in eventos if e["isReveal"]),
        "ceilingsNow": techos_ahora,
        "ceilingsBefore": techos_antes,
        "readings": lecturas,
    }
    return eventos, resumen


async def build_changes_history(
    session: AsyncSession,
    team_id: int,
    player_ht_id: int | None = None,
    *,
    weeks: int = DEFAULT_WINDOW_WEEKS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Cuánto cambió cada jugador en las últimas `weeks` semanas.

    `weeks=SIEMPRE` (0) compara contra el PRIMER cierre guardado de cada
    jugador en vez de contra una fecha común. Ojo con lo que promete esa
    palabra: «siempre» es desde que esta aplicación empezó a mirar, no desde
    que el jugador existe, de quien se compró antes de que existiera HT Lens
    no hay un antes que reconstruir.

    Es una comparación NETA contra el cierre semanal de hace `weeks` semanas,
    no la lista de cada paso intermedio. A una semana da lo mismo, solo hay un
    paso, , pero a dieciséis la diferencia es todo: un jugador que subió tres
    niveles de Pases sale como una línea que dice 8 → 11, no como tres líneas
    sueltas que hay que sumar de cabeza.
    """
    team = await session.get(m.Team, team_id)
    currency_rate = (team.currency_rate or 1.0) if team else 1.0

    # Sólo la plantilla ACTUAL. Las filas `Player` de quien se fue no se borran
    # nunca, son el histórico de traspasos, y se marcan con `left_team_at`.
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
    # caso que `sold_at` en sync_team.py), el cutoff se calcula naive para
    # comparar contra el mismo tipo.
    cutoff = (
        # Con «Siempre» no hay corte: nada es anterior a él, así que `older`
        # sale vacío para todo el mundo y cada jugador cae en su propio primer
        # cierre, que es exactamente lo que se pide.
        datetime.min
        if weeks == SIEMPRE
        else ((now or datetime.now(UTC)) - timedelta(weeks=weeks)).replace(tzinfo=None)
    )

    # Contra qué cierre se compara EL EQUIPO: el más reciente que ya existía
    # cuando empezó la ventana. Se calcula sobre todos los cierres juntos, no
    # jugador a jugador, porque es la respuesta a "¿hace cuánto?" que se
    # enseña en pantalla, un fichaje reciente, que abajo se compara contra su
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

    cantera, resumen_de_cantera = await _cambios_de_cantera(session, team_id, cutoff)
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
        "youthChanges": cantera,
        "youthSummary": resumen_de_cantera,
        "series": series,
    }
