"""Diff de sync: qué cambió desde la última vez.

Esto es una de las cosas que Hattrick Control hace bien: después de cargar
datos, no te obliga a comparar de memoria. Este módulo recibe el estado viejo
y el nuevo, justo durante el sync, y devuelve los cambios detectados.

2026-08-15, corrección de raíz: antes esto devolvía SOLO frases ya
formateadas y el frontend volvía a sacar los números parseando el texto. Eso
se rompió de verdad al unificar el separador de miles: `Number("202.210")`
daba 202,21 y la UI mostraba un TSI de "202". Ahora cada cambio viaja como
`Change`, con los valores numéricos intactos; la frase sigue existiendo
(`summary`) porque es útil para el feed y el CSV, pero ya no es la única
fuente de la información.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.value_objects.formatting import thousands
from app.domain.value_objects.ht_constants import (
    CONFIDENCE,
    SKILL_LABELS,
    TEAM_SPIRIT,
    training_name,
)

ECONOMY_FIELDS: dict[str, str] = {
    "cash": "Caja",
    "supporters_popularity": "Popularidad con la afición",
    "fan_club_size": "Aficionados",
    "income_sum": "Ingresos totales",
    "costs_sum": "Gastos totales",
}
ECONOMY_MONEY_FIELDS = {"cash", "income_sum", "costs_sum"}


@dataclass(frozen=True)
class Change:
    """Un cambio detectado, con el dato crudo Y la frase.

    `summary` la arma quien construye el Change, porque cada tipo de cambio
    tiene su propia redacción ("subió de 10 a 11", "se vendió por X", "TSI
    A -> B") y no vale la pena forzarlas todas a una plantilla común.

    `kind` le dice al frontend CÓMO pintar el par before/after:
      - "count"  → número pelado (TSI, socios, minutos)
      - "money"  → número + moneda
      - "skill"  → nivel 0-20 de habilidad
      - "level"  → nivel con nombre propio (espíritu, confianza, lesión):
                   `before_label`/`after_label` traen el texto
      - "event"  → no hay par numérico (llegó, se vendió, se lesionó)
    """

    category: str
    summary: str
    metric: str = ""
    label: str = ""
    subject: str = ""
    before: float | None = None
    after: float | None = None
    before_label: str | None = None
    after_label: str | None = None
    kind: str = "event"
    good: bool | None = None
    currency: str = ""

    def detail(self) -> dict[str, Any]:
        """Payload que se guarda como JSON junto a la frase. Se omiten las
        claves vacías para no llenar la DB de nulos."""
        raw: dict[str, Any] = {
            "metric": self.metric,
            "label": self.label,
            "subject": self.subject,
            "before": self.before,
            "after": self.after,
            "beforeLabel": self.before_label,
            "afterLabel": self.after_label,
            "kind": self.kind,
            "good": self.good,
            "currency": self.currency,
        }
        return {k: v for k, v in raw.items() if v not in (None, "")}


PLAYER_LEVEL_FIELDS: dict[str, str] = {
    "form": "Forma",
    "stamina": "Resistencia",
    "experience": "Experiencia",
    # Pedido explícito 2026-08-14: de los campos de carácter, estos dos son
    # los que de verdad cambian con el tiempo (fidelidad sube con la
    # antigüedad, liderazgo con el entrenamiento correspondiente) — a
    # diferencia de sociabilidad/agresividad/honestidad, que Hattrick trata
    # como rasgos fijos del jugador.
    "loyalty": "Fidelidad",
    "leadership": "Liderazgo",
}


def diff_player_skills(
    old: dict[str, Any] | None, new: dict[str, Any], player_name: str
) -> list[Change]:
    """Detecta cambios relevantes de jugador.

    `old is None` significa primera vez que vemos al jugador: se anuncia como
    alta de plantilla, no como una lista enorme de "subidas" desde cero.
    """

    def _player(summary: str, **kw: Any) -> Change:
        return Change(category="jugadores", summary=summary, subject=player_name, **kw)

    if old is None:
        return [
            _player(
                f"{player_name} se unió a la plantilla",
                metric="arrival",
                label="Alta",
                kind="event",
            )
        ]

    changes: list[Change] = []
    old_skills = old.get("skills", {}) or {}
    new_skills = new.get("skills", {}) or {}
    for skill, label in SKILL_LABELS.items():
        o, n = old_skills.get(skill), new_skills.get(skill)
        if o is not None and n is not None and o != n:
            verb = "subió" if n > o else "bajó"
            changes.append(
                _player(
                    f"{player_name}: {label} {verb} de {o} a {n}",
                    metric=skill,
                    label=label,
                    before=o,
                    after=n,
                    kind="skill",
                    good=n > o,
                )
            )

    if old.get("tsi") != new.get("tsi"):
        before, after = old.get("tsi", 0), new.get("tsi", 0)
        changes.append(
            _player(
                f"{player_name}: TSI {thousands(before)} -> {thousands(after)}",
                metric="tsi",
                label="TSI",
                before=before,
                after=after,
                kind="count",
                good=after > before,
            )
        )

    if old.get("salary") != new.get("salary"):
        before, after = old.get("salary", 0), new.get("salary", 0)
        changes.append(
            _player(
                f"{player_name}: Salario {thousands(before)} -> {thousands(after)}",
                # Un salario que sube es un gasto que sube: no se marca como bueno.
                metric="salary",
                label="Salario",
                before=before,
                after=after,
                kind="money",
            )
        )

    for field_name, label in PLAYER_LEVEL_FIELDS.items():
        if old.get(field_name) != new.get(field_name):
            before, after = old.get(field_name, 0), new.get(field_name, 0)
            changes.append(
                _player(
                    f"{player_name}: {label} {before} -> {after}",
                    metric=field_name,
                    label=label,
                    before=before,
                    after=after,
                    kind="skill",
                    good=after > before,
                )
            )

    old_injury, new_injury = old.get("injury_level", -1), new.get("injury_level", -1)
    if old_injury != new_injury:
        if new_injury == -1:
            summary, good = f"{player_name}: se recuperó de la lesión", True
        elif old_injury == -1:
            summary, good = f"{player_name}: se lesionó", False
        else:
            summary = f"{player_name}: lesión de nivel {old_injury} a {new_injury}"
            good = new_injury < old_injury
        changes.append(
            _player(
                summary,
                metric="injury",
                label="Lesión",
                before=old_injury,
                after=new_injury,
                kind="level",
                good=good,
            )
        )

    if old.get("is_transfer_listed") != new.get("is_transfer_listed"):
        listed = new.get("is_transfer_listed")
        changes.append(
            _player(
                f"{player_name}: {'puesto en' if listed else 'retirado del'} mercado",
                metric="market",
                label="Mercado",
                kind="event",
                after_label="Puesto en venta" if listed else "Retirado del mercado",
            )
        )

    return changes


def diff_rival_purchase(
    team_name: str,
    player_name: str,
    tsi: int,
    price: int,
    competition: str,
    best_rating: float | None = None,
    currency: str = "",
) -> Change:
    """Un club al que te vas a enfrentar ha fichado — 2026-08-19.

    No es un cambio TUYO, y por eso no vive con los de plantilla: es
    información de la competencia. Lo que importa es a qué nivel compran los
    que tienes enfrente, así que la frase lleva el TSI del fichaje y, si ya ha
    jugado, su mejor nota de los últimos partidos de ese club.

    `best_rating` es `None` cuando el jugador todavía no ha aparecido en
    ninguno: un fichaje de ayer no tiene notas, y fingir un 0 lo haría parecer
    malo en vez de nuevo.
    """
    nota = (
        f", mejor nota reciente {best_rating:.1f}".replace(".", ",")
        if best_rating is not None
        else ", todavía sin jugar"
    )
    return Change(
        category="rivales",
        summary=(
            f"{team_name} ({competition}) fichó a {player_name}: "
            f"TSI {thousands(tsi)}, {thousands(price)} {currency}".strip()
            + nota
        ),
        metric="rival_purchase",
        label="Fichaje rival",
        subject=team_name,
        kind="event",
    )


def diff_player_departure(
    player_name: str,
    sale_price: int | None,
    currency: str = "",
) -> Change:
    """2026-08-12, pedido explícito: un jugador que sale de la plantilla
    (`mark_departed`) no pasaba por `diff_player_skills` — esa función sólo
    compara jugadores que SÍ vienen en el roster nuevo, así que una venta
    real quedaba invisible en "Qué cambió" pese a estar bien guardada en
    `Player.sale_price`/`sold_at`. `sale_price` ya debe venir convertido a
    moneda local (ver `conv()` en player_balance.py) — este módulo no conoce
    la tasa de cambio.

    2026-08-12, corrección pedida explícitamente: NO se anuncia ganancia/
    pérdida aquí. Un delta precio_venta − precio_compra es una cifra sin la
    comisión del agente ni el bono de TSI que sí aplica "Transferencias"
    (`player_balance.py`) — mostrarlo aquí como si fuera el resultado real
    de la venta es engañoso. El precio de venta solo."""
    if not sale_price:
        return Change(
            category="jugadores",
            subject=player_name,
            metric="departure",
            label="Baja",
            kind="event",
            summary=f"{player_name} salió de la plantilla",
        )
    return Change(
        category="jugadores",
        subject=player_name,
        metric="sale",
        label="Venta",
        kind="money",
        after=sale_price,
        currency=currency,
        summary=f"{player_name} se vendió por {thousands(sale_price)} {currency}".strip(),
    )


def diff_previous_club_bonus(
    player_name: str,
    resale_price: int,
    amount: int,
    games: int,
    pct: float,
    currency: str = "",
) -> Change:
    """Alguien revendio a un ex-jugador nuestro y Hattrick nos paga un %.

    2026-08-25, pedido explicitamente: la herramienta encontraba la comision,
    la calculaba al peso y la guardaba SIN DECIR NADA. Era dinero del usuario
    apareciendo en silencio.

    Los dos numeros van juntos a proposito: el precio de la reventa explica de
    donde sale la cifra, y los partidos jugados con nosotros explican por que
    el porcentaje es ese y no otro.
    """
    return Change(
        category="transferencias",
        subject=player_name,
        metric="previous_club_bonus",
        label="Comision de club anterior",
        kind="money",
        after=amount,
        currency=currency,
        summary=(
            f"{player_name} fue revendido por {thousands(resale_price)} {currency}"
            f": te tocan {thousands(amount)} {currency}"
            f" ({pct:.0%} por {games} partidos con nosotros)"
        )
        .replace("  ", " ")
        .strip(),
    )


#: Como se lee cada motivo de cierre en una frase.
MOTIVOS_DE_CIERRE: dict[str, tuple[str, str]] = {
    "entrenador": ("entrenador", "entrenadores"),
    "despedido": ("despedido", "despedidos"),
    "revendido": ("revendido", "revendidos"),
    "sin_comprador": ("sin comprador", "sin comprador"),
}


def diff_expedientes_cerrados(conteo: dict[str, int]) -> Change | None:
    """Cuantos ex-jugadores dejaron de poder darnos dinero, y por que.

    2026-08-25, pedido explicitamente: en "Cambios", TODOS JUNTOS. Un barrido
    completo cierra decenas --en la cuenta real hay 113 revendidos, 87
    despedidos y 41 sin comprador-- y anunciarlos uno a uno enterraria bajo
    doscientas lineas lo que si importa, que es una comision de verdad.

    El detalle de quien fue cual va en el progreso, que es efimero y ahi no
    estorba.
    """
    total = sum(conteo.values())
    if total == 0:
        return None
    partes = []
    for motivo, cuantos in sorted(conteo.items(), key=lambda x: (-x[1], x[0])):
        singular, plural = MOTIVOS_DE_CIERRE.get(motivo, (motivo, motivo))
        partes.append(f"{cuantos} {singular if cuantos == 1 else plural}")
    return Change(
        category="transferencias",
        subject="Vigilancia de comisiones",
        metric="expedientes_cerrados",
        label="Expedientes cerrados",
        kind="count",
        after=total,
        summary=(
            f"{total} expediente{'s' if total != 1 else ''} cerrado"
            f"{'s' if total != 1 else ''}: {', '.join(partes)}"
        ),
    )


def diff_economy(
    old: dict[str, Any] | None, new: dict[str, Any], currency: str = "", rate: float = 1.0
) -> list[Change]:
    """`rate`: CHPP devuelve los montos de economy.xml en la moneda base del
    juego (SEK), no en la local del equipo — corrección 2026-08-05, bug real
    encontrado en vivo: este mensaje mostraba el número crudo en SEK con la
    etiqueta de la moneda LOCAL (p. ej. "10,000 US$" cuando el cambio real,
    dividido por la tasa de Colombia = 10, era 1,000 US$). Mismo criterio
    de conversión que `conv()` en player_balance.py."""
    if old is None:
        return []
    changes: list[Change] = []
    for field_name, label in ECONOMY_FIELDS.items():
        o, n = old.get(field_name), new.get(field_name)
        if o is None or n is None or o == n:
            continue
        if field_name in ECONOMY_MONEY_FIELDS:
            o_conv, n_conv = round(o / rate), round(n / rate)
            if o_conv == n_conv:
                continue  # el cambio crudo en SEK no llega a mover la moneda local
            changes.append(
                Change(
                    category="economía",
                    metric=field_name,
                    label=label,
                    before=o_conv,
                    after=n_conv,
                    kind="money",
                    currency=currency,
                    # "Gastos totales sube" no es bueno; "Caja sube" sí. Los gastos
                    # son el único campo monetario donde más es peor.
                    good=(n_conv < o_conv) if field_name == "costs_sum" else (n_conv > o_conv),
                    summary=(
                        f"{label}: {thousands(o_conv)} -> {thousands(n_conv)} {currency}".strip()
                    ),
                )
            )
        else:
            changes.append(
                Change(
                    category="economía",
                    metric=field_name,
                    label=label,
                    before=o,
                    after=n,
                    kind="count",
                    good=n > o,
                    summary=f"{label}: {o} -> {n}",
                )
            )
    return changes


def diff_training(old: dict[str, Any] | None, new: dict[str, Any]) -> list[Change]:
    if old is None:
        return []
    changes: list[Change] = []
    if old.get("training_type") != new.get("training_type"):
        before, after = old.get("training_type"), new.get("training_type")
        changes.append(
            Change(
                category="entrenamiento",
                metric="training_type",
                label="Tipo",
                before=before,
                after=after,
                kind="count",
                # Con su nombre, no con el número: "tipo 10 -> 2" no lo entiende
                # nadie, y este aviso existe justo para leerse de un vistazo.
                before_label=training_name(before) if before is not None else None,
                after_label=training_name(after) if after is not None else None,
                summary=(
                    f"Entrenamiento: {training_name(before) if before is not None else '?'}"
                    f" -> {training_name(after) if after is not None else '?'}"
                ),
            )
        )
    if old.get("training_level") != new.get("training_level"):
        before, after = old.get("training_level"), new.get("training_level")
        changes.append(
            Change(
                category="entrenamiento",
                metric="training_level",
                label="Nivel de entrenamiento",
                before=before,
                after=after,
                kind="count",
                summary=f"Nivel de entrenamiento: {before} -> {after}",
            )
        )
    old_trainer, new_trainer = old.get("trainer_name", ""), new.get("trainer_name", "")
    if old_trainer != new_trainer and new_trainer:
        changes.append(
            Change(
                category="entrenamiento",
                metric="trainer",
                label="Entrenador",
                kind="event",
                after_label=new_trainer,
                summary=f"Nuevo entrenador: {new_trainer}",
            )
        )
    if old.get("morale") != new.get("morale"):
        before, after = old.get("morale", -1), new.get("morale", -1)
        changes.append(
            Change(
                category="entrenamiento",
                metric="morale",
                label="Espíritu del equipo",
                before=before,
                after=after,
                kind="level",
                good=after > before,
                before_label=str(TEAM_SPIRIT.get(before, before)),
                after_label=str(TEAM_SPIRIT.get(after, after)),
                summary=(
                    f"Espíritu del equipo: {TEAM_SPIRIT.get(before, before)} -> "
                    f"{TEAM_SPIRIT.get(after, after)}"
                ),
            )
        )
    if old.get("self_confidence") != new.get("self_confidence"):
        before = old.get("self_confidence", -1)
        after = new.get("self_confidence", -1)
        changes.append(
            Change(
                category="entrenamiento",
                metric="self_confidence",
                label="Confianza",
                before=before,
                after=after,
                kind="level",
                good=after > before,
                before_label=str(CONFIDENCE.get(before, before)),
                after_label=str(CONFIDENCE.get(after, after)),
                summary=(
                    f"Confianza: {CONFIDENCE.get(before, before)} -> {CONFIDENCE.get(after, after)}"
                ),
            )
        )
    return changes


def diff_standing(old_position: int | None, new_position: int, team_name: str) -> Change | None:
    if old_position is None or old_position == new_position:
        return None
    verb = "subió" if new_position < old_position else "bajó"
    return Change(
        category="liga",
        metric="position",
        label="Posición",
        subject=team_name,
        before=old_position,
        after=new_position,
        kind="count",
        # En una tabla, bajar de número es mejorar.
        good=new_position < old_position,
        summary=f"{team_name} {verb} de la posición {old_position} a la {new_position}",
    )


@dataclass(frozen=True)
class MatchState:
    status: str
    home_goals: int
    away_goals: int


def diff_match(
    before: MatchState | None, after: MatchState, is_home: bool, opponent: str
) -> Change | None:
    """Anuncia solo resultados nuevos; no repite partidos ya conocidos."""
    if before is None or after.status != "FINISHED":
        return None
    if before.status == "FINISHED" and (
        before.home_goals == after.home_goals and before.away_goals == after.away_goals
    ):
        return None

    own_goals = after.home_goals if is_home else after.away_goals
    rival_goals = after.away_goals if is_home else after.home_goals
    if own_goals > rival_goals:
        verdict, good = "Ganaste", True
    elif own_goals < rival_goals:
        verdict, good = "Perdiste", False
    else:
        verdict, good = "Empataste", None
    return Change(
        category="partidos",
        metric="result",
        label="Resultado",
        subject=opponent,
        before=own_goals,
        after=rival_goals,
        kind="event",
        good=good,
        after_label=f"{verdict} {own_goals}-{rival_goals}",
        summary=f"{verdict} {own_goals}-{rival_goals} vs {opponent}",
    )
