"""Insights y alertas — HL-130, HL-131, HL-038, HL-112, HL-114.

La diferencia entre un visor de datos y un asistente: Hattrick Control te da
cuarenta columnas y tú deduces; esto te dice qué hacer y por qué.

Cada insight lleva: severidad, mensaje en lenguaje llano, el dato que lo
sustenta y la acción sugerida. Nada de avisos sin salida.
"""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.engines import weather as wx
from app.domain.value_objects.formatting import thousands
from app.domain.value_objects.ht_constants import skill_name


class Severity(StrEnum):
    INFO = "info"
    OPPORTUNITY = "opportunity"
    WARNING = "warning"
    DANGER = "danger"


@dataclass
class Insight:
    key: str
    severity: Severity
    title: str
    detail: str
    action: str = ""
    module: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


# Todas las claves que este módulo puede emitir, como raíces: varias reglas le
# pegan detrás un sufijo con punto —el id del jugador, del canterano, el sector,
# la semana— así que `player.injured` cubre también `player.injured.474559832`.
#
# Existe porque el buzón guarda una fila por alerta archivada y esa fila
# sobrevive a la regla. Al borrar una regla —o al cambiarle la clave— sus
# archivadas quedan huérfanas: no pueden reaparecer jamás, así que listarlas es
# prometer un aviso que no va a llegar. Con esta lista el buzón puede
# reconocerlas y descartarlas solo, sin que haya que acordarse de purgar la
# base a mano cada vez.
#
# Si añades o renombras una regla, añade aquí su clave — hay un test que
# compara esta lista contra las claves reales del módulo y falla si se olvida.
KNOWN_KEY_ROOTS: frozenset[str] = frozenset({
    "academy.deadline",
    "academy.profitable",
    "academy.prospect",
    "academy.unprofitable",
    "arena.expansion_opportunity",
    "arena.sold_out",
    "economy.cash_below_expected",
    "economy.fan_club_shrinking",
    "economy.income_concentration",
    "economy.structural_deficit",
    "league.next_match_favorite",
    "league.next_match_underdog",
    "league.promotion_chance",
    "league.relegation_danger",
    "league.relegation_playoff_risk",
    "league.title_race",
    "league.weak_attack",
    "league.weak_defence",
    "match.weather",
    "player.form_low",
    "player.injured",
    "player.wage_concentration",
    "squad.ageing",
    "squad.no_natural_keeper",
    "squad.sector_standout",
    "squad.single_keeper",
    "staff.assistants_low",
    "staff.no_medic",
    "staff.no_psychologist",
    "sync.stale",
    "training.inefficient",
})


def is_known_key(key: str) -> bool:
    """¿Puede alguna regla viva volver a emitir esta clave?

    `False` para una archivada huérfana: su regla ya no existe o cambió de
    clave. Nunca volverá a generarse, de modo que quien la guarde puede
    tirarla.
    """
    return any(
        key == root or key.startswith(f"{root}.") for root in KNOWN_KEY_ROOTS
    )


# Reglas cuya clave lleva pegada la semana de temporada. Es deliberado: el
# déficit estructural se juzga semana a semana, así que archivar el de 83-04 no
# puede tapar el de 83-05 — clave distinta, alerta nueva.
#
# El precio de eso es que la archivada de una semana pasada ya no le sirve a
# nadie: esa semana no vuelve, y su clave tampoco. Se caducan.
WEEK_SCOPED_KEY_ROOTS: frozenset[str] = frozenset({
    "economy.structural_deficit",
    # El clima lleva pegado el id del partido por la misma razón: el aviso de
    # mañana es otro aviso, no el de hoy con otra cifra. Y el partido de
    # anteayer ya se jugó, así que su archivada tampoco le sirve a nadie.
    "match.weather",
})


def week_scoped_root(key: str) -> str | None:
    """La raíz semanal a la que pertenece esta clave, si es de las que llevan
    semana pegada. `None` para el resto."""
    for root in WEEK_SCOPED_KEY_ROOTS:
        if key == root or key.startswith(f"{root}."):
            return root
    return None


# ── Entrenamiento ───────────────────────────────────────────────────────────

def inefficient_training(
    trainees: list[dict[str, Any]], age_threshold: int = 27, weeks_threshold: float = 10.0
) -> list[Insight]:
    """HL-038: gastar plazas de entrenamiento en jugadores mayores.

    Caso real que motivó esta regla: entrenar pases con dos jugadores de 27 y 28
    años que tardan 10,8 y 11,7 semanas por nivel, mientras los de 20 tardan 7,5.

    El propio jugador-entrenador no debería llegar a esta lista, pero eso se
    resuelve en la capa que arma `trainees` (sabe quién es el entrenador por
    `training.xml`), no aquí: este motor no tiene por qué conocer el concepto
    de "entrenador", solo evalúa a quien le pasen.
    """
    caros = [t for t in trainees
             if t["age_years"] >= age_threshold and t["weeks_to_pop"] >= weeks_threshold]
    if not caros:
        return []
    peor = max(caros, key=lambda t: t["weeks_to_pop"])
    return [Insight(
        key="training.inefficient",
        severity=Severity.WARNING,
        title=f"{len(caros)} jugador(es) caros de entrenar",
        detail=(
            f"{peor['name']} tiene {peor['age_years']} años y necesita "
            f"{peor['weeks_to_pop']:.1f} semanas por nivel. Un jugador de 20 tarda ~7,5."
        ),
        action=(
            "Compara sus semanas con las de los jóvenes: la fórmula pública "
            "encarece el entrenamiento tanto por edad como por nivel de habilidad."
        ),
        module="entrenamiento",
        evidence={"players": [t["name"] for t in caros]},
    )]


# ── Economía ────────────────────────────────────────────────────────────────

def structural_deficit(
    structural_balance: int, cash: int, currency: str = "", season_week: str | None = None,
) -> list[Insight]:
    """HL-051: la operación pierde dinero aunque el titular sea positivo.

    2026-08-16, pedido explícito: la alerta es POR SEMANA. La temporada-semana
    entra en la clave, así que al cambiar de semana la anterior deja de estar
    activa y nace una nueva aunque las cifras sean idénticas. Perder dinero
    otra semana más es un hecho nuevo, no el mismo de siempre: archivarla una
    vez no puede callar el resto del ejercicio. Las archivadas quedan en el
    buzón como registro de qué semanas diste por enteradas.
    """
    if structural_balance >= 0:
        return []
    semanas = cash // abs(structural_balance) if structural_balance else 999
    sev = Severity.DANGER if semanas < 20 else Severity.WARNING
    return [Insight(
        key=(
            f"economy.structural_deficit.{season_week}"
            if season_week else "economy.structural_deficit"
        ),
        severity=sev,
        title=(
            f"Tu club pierde dinero esta semana ({season_week})"
            if season_week else "Tu club pierde dinero cada semana"
        ),
        detail=(
            f"El balance sin transferencias es {thousands(structural_balance)} {currency} por semana. "
            f"Con la caja actual aguantas unas {semanas} semanas."
        ),
        action="Recorta salarios o sube ingresos: vender jugadores solo tapa el agujero.",
        module="economía",
        evidence={
            "structuralBalance": structural_balance,
            "weeksOfRunway": semanas,
            "seasonWeek": season_week,
        },
    )]


def income_concentration(
    income_items: list[tuple[str, int]], currency: str = "", share_threshold: float = 0.7
) -> list[Insight]:
    """HL-052: cuando casi todo el ingreso depende de una sola fuente
    (típicamente taquilla), un mal fin de semana pesa más de lo normal."""
    total = sum(v for _, v in income_items if v > 0)
    if total <= 0:
        return []
    label, value = max(income_items, key=lambda t: t[1])
    share = value / total
    if share < share_threshold:
        return []
    return [Insight(
        key="economy.income_concentration",
        severity=Severity.INFO,
        title=f"{share:.0%} de tus ingresos vienen de {label.lower()}",
        detail=f"{thousands(value)} {currency} de {thousands(total)} {currency} en la última lectura.",
        action="Diversificar (patrocinios, afición) amortigua una mala racha de resultados.",
        module="economía",
        evidence={"source": label, "share": round(share, 3)},
    )]


def cash_vs_expected_mismatch(
    cash: int, expected_cash: int, currency: str = "", ratio_threshold: float = 1.5
) -> list[Insight]:
    """CHPP reporta `Cash` (hoy) y `ExpectedCash` (proyección propia de
    Hattrick a corto plazo) por separado; cruzarlos es gratis y HC no lo hace."""
    if expected_cash == 0 or cash == 0:
        return []
    ratio = max(cash, expected_cash) / max(min(cash, expected_cash), 1)
    if ratio < ratio_threshold:
        return []
    # 2026-08-16, veredicto del usuario: solo avisa cuando la caja va PEOR.
    # Ir mejor de lo previsto no pide ninguna decisión.
    if cash > expected_cash:
        return []
    return [Insight(
        key="economy.cash_below_expected",
        severity=Severity.WARNING,
        title="Tu caja va peor de lo que Hattrick esperaba",
        detail=(
            f"Caja actual {thousands(cash)} {currency} contra {thousands(expected_cash)} "
            f"{currency} esperados."
        ),
        action="Algo salió peor de lo previsto: revisa fichajes o gastos recientes.",
        module="economía",
        evidence={"cash": cash, "expectedCash": expected_cash},
    )]


def fan_club_trend(previous: int, latest: int, drop_ratio: float = 0.05) -> list[Insight]:
    """Ídem: la peña de aficionados es un conteo real, y una caída relativa
    (no un umbral absoluto inventado) es lo que se puede afirmar con datos
    propios."""
    if previous <= 0:
        return []
    delta = (latest - previous) / previous
    if delta <= -drop_ratio:
        return [Insight(
            key="economy.fan_club_shrinking",
            severity=Severity.INFO,
            title="Tu peña de aficionados está encogiendo",
            detail=(
                f"Bajó de {thousands(previous)} a {thousands(latest)} desde la última lectura "
                f"({delta:.0%})."
            ),
            action="",
            module="economía",
            evidence={"previous": previous, "latest": latest},
        )]
    return []


# ── Estadio ─────────────────────────────────────────────────────────────────

def sold_out_sectors(sold_out: list[str], lost_revenue: float, currency: str = "") -> list[Insight]:
    """HL-061: demanda censurada — estás dejando gente fuera."""
    if not sold_out:
        return []
    return [Insight(
        key="arena.sold_out",
        severity=Severity.OPPORTUNITY,
        title=f"{len(sold_out)} sector(es) agotados en el estadio",
        detail=(
            "La asistencia observada ya no mide tu demanda real: está limitada por la "
            f"capacidad. Además dejas de ingresar {thousands(lost_revenue)} {currency} por "
            "asientos vacíos en otros sectores."
        ),
        action="Valora ampliar los sectores que se llenan, no los que sobran.",
        module="estadio",
        evidence={"soldOut": sold_out},
    )]


def arena_expansion_opportunity(
    options: list[dict[str, Any]], currency: str = "", max_payback_seasons: float = 6.0
) -> list[Insight]:
    """HL-064: de las opciones ya evaluadas por el simulador de ampliación,
    ¿hay alguna que se amortice en un plazo razonable?"""
    viables = [
        o for o in options
        if o.get("netPerSeason", 0) > 0 and o.get("paybackSeasons") is not None
        and o["paybackSeasons"] <= max_payback_seasons
    ]
    if not viables:
        return []
    best = min(viables, key=lambda o: o["paybackSeasons"])
    return [Insight(
        key="arena.expansion_opportunity",
        severity=Severity.OPPORTUNITY,
        title="Ampliar el estadio compensaría",
        detail=(
            f"{best['label']}: se amortizaría en ~{best['paybackSeasons']:.1f} temporadas, "
            f"con un neto de {thousands(best['netPerSeason'])} {currency}/temporada."
        ),
        action="Revisa el simulador de ampliación para ver el resto de opciones.",
        module="estadio",
        evidence={"option": best["label"], "paybackSeasons": best["paybackSeasons"]},
    )]


# ── Plantilla ───────────────────────────────────────────────────────────────

def ageing_squad(
    players: list[dict[str, Any]], threshold: int = 32, top_n: int = 11, minimum: int = 3,
) -> list[Insight]:
    """2026-08-16, redefinida por el usuario: mira solo a los `top_n` de más
    TSI, no a la plantilla entera.

    Que envejezcan los suplentes no obliga a nada; que envejezca el once que
    de verdad juega, sí. Antes bastaban tres jugadores de 30+ en cualquier
    parte del plantel y eso se cumplía casi siempre, incluso con un equipo
    joven cargado de veteranos de banquillo.
    """
    core = sorted(players, key=lambda p: p.get("tsi", 0), reverse=True)[:top_n]
    viejos = [p for p in core if p["age_years"] >= threshold]
    if len(viejos) < minimum:
        return []
    return [Insight(
        key="squad.ageing",
        severity=Severity.INFO,
        title=f"{len(viejos)} de tus {top_n} jugadores de más TSI tienen {threshold}+ años",
        detail=", ".join(p["name"] for p in viejos),
        action="Revisa su ventana de venta: el valor de mercado cae rápido a esta edad.",
        module="equipo",
        evidence={"players": [p["name"] for p in viejos], "topN": top_n},
    )]


def injuries(players: list[dict[str, Any]]) -> list[Insight]:
    """Bajas reales, una alerta por jugador.

    `InjuryLevel` 0 es MAGULLADO y puede jugar, así que no es una baja y no
    genera aviso; a partir de 1 son semanas de baja. Antes bastaba con estar
    magullado para salir aquí como "lesionado".

    Una alerta por cabeza (2026-08-16, pedido explícito): agrupadas en una
    sola, un segundo lesionado no se distinguía del primero — la alerta ya
    archivada seguía tapando la novedad.
    """
    out: list[Insight] = []
    for p in players:
        weeks = p.get("injury_level", -1)
        if weeks >= 1:
            out.append(Insight(
                key=f"player.injured.{p['ht_player_id']}",
                severity=Severity.WARNING,
                title=f"{p['name']} está lesionado",
                detail=f"Le quedan {weeks} semana(s) de baja.",
                action="El optimizador ya lo deja fuera del once mientras dure.",
                module="equipo",
                evidence={"player": p["name"], "weeks": weeks},
            ))
    return out


def low_form(players: list[dict[str, Any]]) -> list[Insight]:
    """Forma baja, jugador a jugador — no un resumen, una alerta con nombre.

    Umbral relativo a la misma escala de habilidad que usa el resto de la
    herramienta (`skill_name`, 0-20): 4 o menos es un nivel en el que el
    jugador rinde por debajo de lo que dicen sus habilidades.
    """
    out: list[Insight] = []
    for p in players:
        form = p.get("form", -1)
        # 2026-08-16, umbral fijado por el usuario: primero de 2 a 5, luego a 4.
        if 0 <= form <= 4:
            out.append(Insight(
                key=f"player.form_low.{p['ht_player_id']}",
                severity=Severity.WARNING,
                title=f"{p['name']} está en {skill_name(form)} forma",
                detail=(
                    f"Forma {form}: mientras dure, rinde claramente por debajo de lo "
                    "que sus habilidades prometen."
                ),
                action="Evita depender de él en un partido decisivo hasta que se recupere.",
                module="equipo",
                evidence={"player": p["name"], "form": form},
            ))
    return out


def wage_concentration(
    players: list[dict[str, Any]], total_salary: int, currency: str = "",
    share_threshold: float = 0.15,
) -> list[Insight]:
    """Un único jugador cargando una parte desproporcionada de la nómina."""
    if total_salary <= 0:
        return []
    out: list[Insight] = []
    for p in players:
        share = p.get("salary_local", 0) / total_salary
        if share >= share_threshold:
            out.append(Insight(
                key=f"player.wage_concentration.{p['ht_player_id']}",
                severity=Severity.WARNING,
                title=f"{p['name']} se lleva {share:.0%} de la nómina",
                detail=(
                    f"{thousands(p['salary_local'])} {currency} por semana de un total de "
                    f"{thousands(total_salary)} {currency}."
                ),
                action=(
                    "Si se lesiona o baja de forma, el golpe al balance es grande y concentrado."
                ),
                module="economía",
                evidence={"player": p["name"], "share": round(share, 3)},
            ))
    return out


def thin_keeper_depth(players: list[dict[str, Any]]) -> list[Insight]:
    """Cuántos jugadores tienen la portería como su mejor posición natural.
    Sin ninguno el riesgo es estructural; con uno solo, no hay recambio."""
    porteros = [p for p in players if p.get("best_position") == "keeper"]
    if len(porteros) >= 2:
        return []
    if not porteros:
        return [Insight(
            key="squad.no_natural_keeper",
            severity=Severity.DANGER,
            title="Ningún jugador tiene la portería como mejor posición",
            detail="Todo tu once sale de jugadores de campo jugando fuera de su puesto natural.",
            action="Ficha o forma un portero: es la posición más difícil de improvisar.",
            module="equipo",
        )]
    return [Insight(
        key="squad.single_keeper",
        severity=Severity.WARNING,
        title="Un solo portero natural en la plantilla",
        detail=f"{porteros[0]['name']} es tu único jugador con la portería como mejor posición.",
        action="Sin suplente natural, una lesión suya te obliga a improvisar.",
        module="equipo",
        evidence={"player": porteros[0]["name"]},
    )]


def sector_standouts(standouts: list[dict[str, Any]]) -> list[Insight]:
    """HL-143: quién es tu principal aportador por sector, según la fórmula
    exacta de contribución posicional — un dato que solo existía enterrado
    en la tabla de la alineación. `standouts`: uno por sector, ya resuelto
    (sector, label, player, positionLabel, amount)."""
    return [
        Insight(
            key=f"squad.sector_standout.{s['sector']}",
            severity=Severity.INFO,
            title=f"{s['player']} es tu principal aportador en {s['label']}",
            detail=f"Jugando de {s['positionLabel']}, aporta {s['amount']:.1f} al sector.",
            action="",
            module="equipo",
            evidence={"sector": s["sector"], "player": s["player"], "amount": s["amount"]},
        )
        for s in standouts
    ]


# ── Academia ────────────────────────────────────────────────────────────────

def academy_roi(invested: int, earned: int, currency: str = "") -> list[Insight]:
    """HL-114: ¿ha sido rentable la cantera? HC muestra ambos números sin cruzarlos."""
    neto = earned - invested
    if invested == 0:
        return []
    if neto >= 0:
        return [Insight(
            key="academy.profitable",
            severity=Severity.INFO,
            title="Tu academia ha sido rentable",
            detail=f"Invertido {thousands(invested)} {currency}, generado {thousands(earned)} {currency}.",
            action="",
            module="academia",
            evidence={"invested": invested, "earned": earned, "net": neto},
        )]
    return [Insight(
        key="academy.unprofitable",
        severity=Severity.WARNING,
        title="Tu academia no ha recuperado la inversión",
        detail=(
            f"Llevas {thousands(invested)} {currency} invertidos y has generado "
            f"{thousands(earned)}. Diferencia: {thousands(neto)}."
        ),
        action="Decide si el proyecto de cantera compensa o si ese dinero rinde más en el mercado.",
        module="academia",
        evidence={"invested": invested, "earned": earned, "net": neto},
    )]


def youth_deadline(youths: list[dict[str, Any]], days_warning: int = 21) -> list[Insight]:
    """HL-112: fecha límite de promoción. En HC está escondido en una pestaña."""
    urgentes = [y for y in youths if 0 < y.get("days_until_deadline", 999) <= days_warning]
    if not urgentes:
        return []
    y = min(urgentes, key=lambda x: x["days_until_deadline"])
    return [Insight(
        key="academy.deadline",
        severity=Severity.DANGER,
        title=f"{len(urgentes)} juvenil(es) a punto de perderse",
        detail=f"A {y['name']} le quedan {y['days_until_deadline']} días para promocionar.",
        action="Promociónalo antes de la fecha límite o lo perderás.",
        module="academia",
        evidence={"players": [u["name"] for u in urgentes]},
    )]


def youth_star_prospect(youths: list[dict[str, Any]]) -> list[Insight]:
    """HL-111, jugador a jugador: distingue una promesa concreta del ruido
    de la lista completa de juveniles — solo categorías altas y con
    veredicto ya no provisional (suficientes skills reveladas)."""
    out: list[Insight] = []
    for y in youths:
        if y.get("category") in ("crack", "promesa") and not y.get("verdict_is_provisional"):
            out.append(Insight(
                key=f"academy.prospect.{y['ht_youth_player_id']}",
                severity=Severity.OPPORTUNITY,
                title=f"{y['name']} apunta a {y['category']} de la academia",
                detail=(
                    f"Mejor habilidad: {y['best_skill']} "
                    f"(techo {y['best_skill_max'] if y['best_skill_max'] is not None else '?'})."
                ),
                action=y.get("promote_advice", ""),
                module="academia",
                evidence={"player": y["name"], "category": y["category"]},
            ))
    return out


# ── Liga ────────────────────────────────────────────────────────────────────
# Todas evalúan solo el outlook DEL PROPIO equipo (own_outlook): son alertas
# para decidir algo, no un boletín sobre el resto de la serie.

def relegation_danger(own: dict[str, Any], threshold: float = 0.4) -> list[Insight]:
    """HL-090: descenso directo (7º-8º), ya filtrado por si hay a dónde
    descender — `season_simulator` devuelve 0 en la última división."""
    p = own.get("relegation_probability", 0.0)
    if p < threshold:
        return []
    return [Insight(
        key="league.relegation_danger",
        severity=Severity.DANGER,
        title=f"{p:.0%} de probabilidad de descenso directo",
        detail=f"Posición esperada: {own.get('expected_position')}.",
        action="Revisa refuerzos o ajustes tácticos antes de que se acabe la temporada.",
        module="liga",
        evidence={"relegationProbability": p},
    )]


def relegation_playoff_risk(own: dict[str, Any], threshold: float = 0.35) -> list[Insight]:
    """HL-090: puesto 5º-6º, promoción para NO descender — no es lo mismo
    que ascender, y season_simulator ya lo etiqueta así."""
    p = own.get("relegation_playoff_probability", 0.0)
    if p < threshold:
        return []
    return [Insight(
        key="league.relegation_playoff_risk",
        severity=Severity.WARNING,
        title=f"{p:.0%} de probabilidad de jugar promoción para no descender",
        detail=f"Posición esperada: {own.get('expected_position')}.",
        action="Un puesto 5º-6º no es zona cómoda: toca jugar una promoción para salvarse.",
        module="liga",
        evidence={"relegationPlayoffProbability": p},
    )]


def promotion_chance(own: dict[str, Any], threshold: float = 0.4) -> list[Insight]:
    """`promotion_probability` es en realidad P(terminar 1º) — idéntica a
    `title_probability`, ver season_simulator.py. El 1º de una división
    intermedia asciende directo o juega promoción según el ranking nacional
    de campeones, que ningún fichero CHPP expone — así que el título de
    este insight no puede prometer "ascenso" sin más."""
    p = own.get("promotion_probability", 0.0)
    if p < threshold:
        return []
    return [Insight(
        key="league.promotion_chance",
        severity=Severity.OPPORTUNITY,
        title=f"{p:.0%} de probabilidad de terminar 1º",
        detail=(
            f"Posición esperada: {own.get('expected_position')}. El ascenso "
            "directo o la promoción dependen del ranking nacional de "
            "campeones, no modelado."
        ),
        action="Con opciones reales de terminar 1º, cada punto pesa más de lo habitual.",
        module="liga",
        evidence={"promotionProbability": p},
    )]


def title_race(own: dict[str, Any], threshold: float = 0.25) -> list[Insight]:
    p = own.get("title_probability", 0.0)
    if p < threshold:
        return []
    return [Insight(
        key="league.title_race",
        severity=Severity.OPPORTUNITY,
        title=f"{p:.0%} de probabilidad de terminar campeón",
        detail=f"Puntos esperados: {own.get('expected_points')}.",
        action="",
        module="liga",
        evidence={"titleProbability": p},
    )]


def weak_attack(own: dict[str, Any], threshold: float = 0.8) -> list[Insight]:
    """`attack_strength` de `season_simulator`: 1,0 es exactamente la media
    de la liga, encogido bayesianamente — por debajo de este umbral el
    equipo marca claramente menos que un rival medio."""
    a = own.get("attack_strength", 1.0)
    if a >= threshold:
        return []
    return [Insight(
        key="league.weak_attack",
        severity=Severity.WARNING,
        title="Tu ataque rinde por debajo de la media de la liga",
        detail=f"Fuerza de ataque {a:.2f} (1,00 = media de {own.get('name', 'la serie')}).",
        action="El simulador de temporada lo penaliza en cada posición esperada.",
        module="liga",
        evidence={"attackStrength": a},
    )]


def weak_defence(own: dict[str, Any], threshold: float = 1.25) -> list[Insight]:
    """`defence_strength` es goles EN CONTRA sobre la media de la liga, así que
    más alto es peor: 1,25 significa encajar un 25% por encima del promedio.

    2026-08-16: el usuario pidió "<0,8" para igualar el umbral del ataque,
    pero aplicado tal cual dispararía con las MEJORES defensas. 1,25 es el
    espejo real de "ataque <0,80" en esta escala multiplicativa (1/0,8), que
    era la intención.
    """
    d = own.get("defence_strength", 1.0)
    if d <= threshold:
        return []
    return [Insight(
        key="league.weak_defence",
        severity=Severity.WARNING,
        title="Tu defensa encaja por encima de la media de la liga",
        detail=f"Fuerza de defensa {d:.2f} (1,00 = media; más alto es peor).",
        action="",
        module="liga",
        evidence={"defenceStrength": d},
    )]


def next_match_forecast(next_match: dict[str, Any], edge_threshold: float = 0.55) -> list[Insight]:
    """HL-094: pronóstico del propio simulador Poisson para el próximo
    partido de liga — favorito claro (rotar sin miedo) o claro perdedor
    (reforzar), nunca ambos a la vez.

    `next_match` llega tal cual lo arma `LeagueQueryService` (claves
    camelCase, no snake_case como el resto de este motor): es un dict ya
    construido para la API, no un DTO propio del dominio.
    """
    is_home = next_match.get("isHome", True)
    own_win = next_match.get("homeWin") if is_home else next_match.get("awayWin")
    rival_win = next_match.get("awayWin") if is_home else next_match.get("homeWin")
    rival = next_match.get("away") if is_home else next_match.get("home")
    if own_win is None or rival_win is None:
        return []
    if own_win >= edge_threshold:
        return [Insight(
            key="league.next_match_favorite",
            severity=Severity.OPPORTUNITY,
            title=f"Favorito claro contra {rival}",
            detail=(
                f"El modelo te da {own_win:.0%} de ganar "
                f"(empate {next_match.get('draw', 0):.0%})."
            ),
            action="Puede ser un buen partido para rotar o descansar a alguien tocado.",
            module="liga",
            evidence={"opponent": rival, "ownWin": own_win},
        )]
    if rival_win >= edge_threshold:
        return [Insight(
            key="league.next_match_underdog",
            severity=Severity.WARNING,
            title=f"El modelo te da como no favorito contra {rival}",
            detail=f"{rival_win:.0%} de que gane el rival, contra tu {own_win:.0%}.",
            action="Es forma agregada, no el partido concreto: no dejes de preparar el choque.",
            module="liga",
            evidence={"opponent": rival, "rivalWin": rival_win},
        )]
    return []


def next_match_weather(
    ht_match_id: int,
    rival: str,
    is_home: bool,
    region_name: str,
    weather_id: int,
    *,
    tomorrow: bool,
) -> list[Insight]:
    """El clima de la región donde se juega el próximo partido — 2026-08-18.

    Hattrick pronostica a un día vista, así que este aviso solo aparece la
    víspera o el mismo día. Sirve para lo único que el clima decide de verdad:
    qué especialidades rinden un 5% por encima o por debajo de lo normal.

    Con nublado o parcialmente nublado el aviso también sale, y dice justo eso:
    que no hay nada que ajustar. Callar sería dejar al manager preguntándose si
    el dato faltaba o si no había efecto.
    """
    if weather_id not in wx.WEATHER_NAMES:
        return []
    cuando = "mañana" if tomorrow else "hoy"
    sede = "en casa" if is_home else f"en casa de {rival}"
    icono = wx.WEATHER_ICONS.get(weather_id, "")
    suben = wx.favoured(weather_id)
    bajan = wx.hindered(weather_id)
    pct = f"{wx.EFFECT_PCT:.0%}"

    if wx.is_neutral(weather_id):
        detalle = (
            f"Se juega {sede}, en {region_name}. "
            "Ese cielo no favorece ni penaliza a ninguna especialidad."
        )
        accion = "Alinea por criterio deportivo: el clima no entra en la cuenta."
    else:
        detalle = (
            f"Se juega {sede}, en {region_name}. "
            f"Suben un {pct} en todas sus habilidades: {', '.join(suben)}. "
            f"Bajan un {pct}: {', '.join(bajan)}."
        )
        accion = (
            f"Si tienes a alguien {suben[0].lower()} en la banca, "
            "este es su partido."
        )
    return [Insight(
        key=f"match.weather.{ht_match_id}",
        severity=Severity.INFO,
        title=f"{icono} {wx.weather_name(weather_id)} {cuando} contra {rival}",
        detail=detalle,
        action=accion,
        module="partidos",
        evidence={
            "htMatchId": ht_match_id,
            "regionName": region_name,
            "weatherId": weather_id,
            "weatherName": wx.weather_name(weather_id),
            "favoured": suben,
            "hindered": bajan,
            "isHome": is_home,
            "playedTomorrow": tomorrow,
            "venue": sede,
        },
    )]


# ── Copa ────────────────────────────────────────────────────────────────────

# ── Cuerpo técnico ──────────────────────────────────────────────────────────

def missing_medic_or_psych(staff: dict[str, Any]) -> list[Insight]:
    """`medic_levels`/`sport_psychologist_levels` en 0 es un hecho binario
    (contratado o no), no un umbral inventado."""
    out: list[Insight] = []
    if staff.get("medic_levels", 0) == 0:
        out.append(Insight(
            key="staff.no_medic",
            severity=Severity.INFO,
            title="Sin médico en el cuerpo técnico",
            detail="El nivel de médico reportado por CHPP es 0.",
            action="Afecta a los tiempos de recuperación de lesión.",
            module="staff",
        ))
    if staff.get("sport_psychologist_levels", 0) == 0:
        out.append(Insight(
            key="staff.no_psychologist",
            severity=Severity.INFO,
            title="Sin psicólogo deportivo en el cuerpo técnico",
            detail="El nivel de psicólogo deportivo reportado por CHPP es 0.",
            action="",
            module="staff",
        ))
    return out


def assistant_trainers_below_reference(staff: dict[str, Any], reference: int = 10) -> list[Insight]:
    """`reference=10` no es un umbral inventado para esta regla: es la misma
    suposición que usa `TrainingSetup` en el resto de la herramienta cuando
    no hay dato mejor — comparar contra ella es coherente con lo que ya
    asume el motor de entrenamiento."""
    level = staff.get("assistant_trainer_levels", 0)
    if level >= reference:
        return []
    return [Insight(
        key="staff.assistants_low",
        severity=Severity.INFO,
        title="Ayudantes de entrenador por debajo del nivel de referencia",
        detail=(
            f"Suma de niveles de ayudantes: {level} "
            f"(referencia usada en el resto de la app: {reference})."
        ),
        action="Más nivel de ayudantes acelera el entrenamiento de toda la plantilla.",
        module="staff",
        evidence={"assistantTrainerLevels": level},
    )]


# ── Sincronización ──────────────────────────────────────────────────────────

def stale_data(hours_since_sync: float, threshold: float = 24.0) -> list[Insight]:
    if hours_since_sync < threshold:
        return []
    return [Insight(
        key="sync.stale",
        severity=Severity.INFO,
        title="Tus datos tienen más de un día",
        detail=f"Última sincronización hace {hours_since_sync:.0f} horas.",
        action="Pulsa Sincronizar para traer lo último desde Hattrick.",
        module="general",
    )]


ORDER = {Severity.DANGER: 0, Severity.WARNING: 1, Severity.OPPORTUNITY: 2, Severity.INFO: 3}


def collect(*groups: list[Insight]) -> list[Insight]:
    """Reúne y ordena por urgencia. HL-130."""
    out: list[Insight] = []
    for g in groups:
        out.extend(g)
    return sorted(out, key=lambda i: ORDER[i.severity])
