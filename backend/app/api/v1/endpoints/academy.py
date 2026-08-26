"""Juveniles. HL-110, HL-111, HL-112, HL-114, HL-115."""

from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.academy import AcademyQueryService
from app.domain.engines import youth_skill_score as yss
from app.domain.engines.youth_training_plan import (
    ENTRENAMIENTOS,
    mejor_variante,
    youth_training_plan,
)
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/academy",
    summary="Canteranos, plazos y retorno de la academia",
    dependencies=[Depends(require_team_owner)],
)
async def academy(team_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Cruza lo invertido con lo ingresado, que es lo que nadie cruza.

    El gasto de la academia es semanal y silencioso y el retorno llega
    temporadas después, en otra pantalla. Aquí van juntos. Y un techo que el
    ojeador no ha revelado se trata como desconocido, no como bajo: descartar
    una promesa por falta de información sería confundir ignorancia con
    evidencia.
    """
    data = await AcademyQueryService(session).get(team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return cast(dict[str, Any], _camel(asdict(data)))


#: A que columna del banquillo va cada uno, por la habilidad en la que mas
#: destaca. Hattrick no le asigna puesto a un juvenil, asi que esto es una
#: lectura: quien apunta a defensa se sienta con los defensas.
COLUMNA_POR_HABILIDAD: dict[str, str] = {
    "keeper": "Portero",
    "defending": "Defensa Central",
    "winger": "Extremo",
    "playmaking": "Medio Centro",
    "passing": "Medio Centro",
    "scoring": "Delantero",
}


def _columna_de_banquillo(mejor_habilidad: str | None) -> str:
    """Sin habilidad destacada no hay columna que adivinar: va a «Extra»."""
    return COLUMNA_POR_HABILIDAD.get(mejor_habilidad or "", "Extra")


def _pareja_sugerida(rows: list[Any]) -> dict[str, Any] | None:
    """Que entrenar de principal y de secundario, con la forma que encaja."""
    if len(rows) < 2:
        return None
    principal, segunda = rows[0], rows[1]
    codigo = mejor_variante(principal.skill, segunda.skill)
    variante = ENTRENAMIENTOS.get(codigo)
    # El reparto de verdad, no el solape de PUESTOS: la frase promete un
    # numero y al pulsar el boton se ve la cancha, y los dos tienen que decir
    # lo mismo. Un puesto de la interseccion que nadie ocupa no es una racion
    # doble.
    plan = youth_training_plan(
        principal.skill,
        codigo,
        principal.players,
        segunda.players,
        tope_principal={p.name for p in principal.at_max},
        tope_secundaria={p.name for p in segunda.at_max},
    )
    return {
        "main": principal.skill,
        "mainLabel": principal.label,
        "secondary": codigo,
        "secondaryLabel": variante.label if variante else segunda.label,
        "secondarySkill": segunda.skill,
        # Cuantos recibirian las dos cosas con esa pareja, y por cuantas
        # semanas: es lo que justifica elegir una forma y no otra.
        "bothCount": plan.con_doble,
    }


def _cobertura_del_ojeador(rows: list[Any]) -> dict[str, Any]:
    """Cuantas lecturas ha dado el ojeador, de todas las que hay.

    Una lectura es un par jugador-habilidad. Cuenta como revelada si se sabe
    el nivel, el techo, o que ya toco techo --las tres son informacion--.
    """
    revelados = total = 0
    en_blanco: dict[str, int] = {}
    for fila in rows:
        for p in list(fila.players) + list(fila.at_max):
            total += 1
            if p.current is not None or p.maximum is not None or p.max_reached:
                revelados += 1
            else:
                en_blanco[p.name] = en_blanco.get(p.name, 0) + 1
    # Un canterano "en blanco" es el que no tiene NI UNA lectura en las siete.
    sin_nada = sorted(n for n, cuantas in en_blanco.items() if cuantas == len(yss.SKILLS))
    return {"known": revelados, "total": total, "blankPlayers": sin_nada}


@router.get(
    "/teams/{team_id}/academy/training-plan",
    summary="El once juvenil con los dos entrenamientos repartidos",
    dependencies=[Depends(require_team_owner)],
)
async def academy_training_plan(
    team_id: int,
    main: str = Query(..., description="Entrenamiento principal"),
    secondary: str = Query(..., description="Entrenamiento secundario"),
    soon_max_days: int = Query(yss.SOON_MAX_DAYS, ge=0, le=112),
    weight_base: float = Query(
        yss.DEFAULT_WEIGHT_BASE, ge=yss.MIN_WEIGHT_BASE, le=yss.MAX_WEIGHT_BASE
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Quién ocupa cada plaza cuando se entrenan dos cosas a la vez.

    Los dos entrenamientos dibujan un diagrama de Venn sobre los PUESTOS del
    campo. La intersección --los que reciben los dos-- se llena primero
    con los mejores del principal; ver `youth_training_plan`.
    """
    for nombre, valor in (("main", main), ("secondary", secondary)):
        # Vale una habilidad a secas --«passing»-- o un entrenamiento concreto
        # --«passing_defenders»--: la sugerencia manda el segundo.
        if valor not in yss.SKILLS and valor not in ENTRENAMIENTOS:
            raise HTTPException(422, f"{nombre}: «{valor}» no es un entrenamiento")

    service = AcademyQueryService(session)
    rows = await service.skill_scores(
        team_id,
        soon_max_days=soon_max_days,
        weight_base=weight_base,
    )
    if rows is None:
        raise HTTPException(404, f"team {team_id} sin canteranos")
    por_habilidad = {r.skill: r for r in rows}

    def habilidad_de(clave: str) -> str:
        e = ENTRENAMIENTOS.get(clave)
        return e.skill if e else clave

    skill_main, skill_sec = habilidad_de(main), habilidad_de(secondary)
    if skill_main not in por_habilidad or skill_sec not in por_habilidad:
        raise HTTPException(404, "no hay canteranos con esas habilidades")

    academia = await service.get(team_id)
    mejores = {j.name: j.best_skill for j in (academia.players if academia else [])}
    # Las siete lecturas de cada canterano, para poder ensenar en la tabla el
    # nivel de LAS DOS habilidades que se entrenan --no solo la que le dio la
    # plaza-- y donde le queda techo por descubrir.
    lecturas = {
        j.name: {r.skill: r for r in j.skills} for j in (academia.players if academia else [])
    }

    plan = youth_training_plan(
        main,
        secondary,
        por_habilidad[skill_main].players,
        por_habilidad[skill_sec].players,
        tope_principal={p.name for p in por_habilidad[skill_main].at_max},
        tope_secundaria={p.name for p in por_habilidad[skill_sec].at_max},
    )
    etiquetas = {r.skill: r.label for r in rows}

    def etiqueta_de(clave: str, skill: str) -> str:
        e = ENTRENAMIENTOS.get(clave)
        return e.label if e else etiquetas.get(skill, skill)

    def _lectura(nombre: str, skill: str) -> dict[str, Any]:
        r = lecturas.get(nombre, {}).get(skill)
        return {
            "label": etiquetas.get(skill, skill),
            "current": r.current if r else None,
            "maximum": r.maximum if r else None,
            "max_reached": bool(r.max_reached) if r else False,
        }

    def _con_habilidad(a: Any) -> dict[str, Any]:
        skill = habilidad_de(a.elegido_por)
        # Donde todavia puede crecer sin que nadie sepa cuanto: el techo sin
        # revelar es la unica pista de potencial que queda. Si ya no queda
        # ninguno, es que el ojeador termino con el.
        sin_techo = [
            etiquetas.get(sk, sk)
            for sk, r in lecturas.get(a.player, {}).items()
            if r.maximum is None and not r.max_reached
        ]
        return {
            **asdict(a),
            "skill_label": etiquetas.get(skill, skill),
            "main_level": _lectura(a.player, skill_main),
            "secondary_level": _lectura(a.player, skill_sec),
            "open_ceilings": sin_techo,
        }

    return cast(
        dict[str, Any],
        _camel(
            {
                "main": main,
                "mainLabel": etiqueta_de(main, skill_main),
                "secondary": secondary,
                "secondaryLabel": etiqueta_de(secondary, skill_sec),
                "doubleCount": plan.con_doble,
                "doubleBlind": plan.doble_a_ciegas,
                # Cuanto ha revelado el ojeador en toda la academia. Sin esto la
                # cancha llena de "desconocido" parece un fallo nuestro, y es el
                # estado real: aqui casi nada esta revelado todavia.
                "scouting": _cobertura_del_ojeador(rows),
                # `skillLabel` es DE QUE habilidad es el nivel que lleva cada fila:
                # cambia por region --la principal arriba, la secundaria en su
                # tramo-- y sin decirlo la columna "Nivel" no significa nada.
                "assignments": [_con_habilidad(a) for a in plan.asignaciones],
                # El banquillo: los que no entraron, con lo mismo que llevan los de
                # dentro y la columna en que caen. Un juvenil no tiene puesto asignado
                # en Hattrick, asi que la columna sale de la habilidad en la que mas
                # destaca --es una lectura nuestra, no un dato del juego.
                "outside": [
                    {
                        **_con_habilidad(a),
                        "benchColumn": _columna_de_banquillo(mejores.get(a.player)),
                    }
                    for a in plan.fuera
                ],
            }
        ),
    )


@router.get(
    "/teams/{team_id}/academy/scouts",
    summary="Quién trajo a cada canterano y qué queda por revelarle",
    dependencies=[Depends(require_team_owner)],
)
async def academy_scouts(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """El informe del ojeador, tal cual lo escribió.

    CHPP no publica una lista de ojeadores --`youthscouts`, `youthscoutlist` y
    `scouts` devuelven 401--, así que lo único que existe es el `ScoutCall` de
    cada canterano: quién lo encontró, dónde estaba ojeando y qué dijo. Con
    eso se puede agrupar por ojeador, que es lo más parecido a "mis
    ojeadores" que hay.
    """
    import json as _json

    from sqlalchemy import select

    from app.application.queries.team_overview import SKILL_LABELS
    from app.infrastructure.db import models as m

    filas = (
        await session.execute(
            select(m.YouthPlayer, m.YouthScoutReport)
            .join(
                m.YouthScoutReport,
                m.YouthScoutReport.youth_player_id == m.YouthPlayer.id,
            )
            .where(m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None))
        )
    ).all()

    etiquetas = {s_: SKILL_LABELS.get(s_, s_) for s_ in yss.SKILLS}
    jugadores = []
    for juvenil, informe in filas:
        puede = _json.loads(informe.may_unlock_json or "{}")
        jugadores.append(
            {
                "name": f"{juvenil.first_name} {juvenil.last_name}".strip(),
                "htYouthPlayerId": juvenil.ht_youth_player_id,
                "arrivedAt": juvenil.arrived_at.isoformat() if juvenil.arrived_at else None,
                "scoutId": informe.scout_id,
                "scoutName": informe.scout_name or "sin nombre",
                "scoutingRegionId": informe.scouting_region_id,
                "comments": [c.get("text", "") for c in _json.loads(informe.comments_json or "[]")],
                # A que habilidades les queda algo por revelar, dicho por el juego
                # y no supuesto por nosotros.
                "mayUnlock": [etiquetas[k] for k, v in puede.items() if v and k in etiquetas],
                "fetchedAt": informe.fetched_at.isoformat() if informe.fetched_at else None,
            }
        )
    jugadores.sort(key=lambda j: (j["scoutName"], j["name"]))

    ojeadores: dict[int | None, dict[str, Any]] = {}
    for j in jugadores:
        o = ojeadores.setdefault(
            j["scoutId"],
            {
                "scoutId": j["scoutId"],
                "scoutName": j["scoutName"],
                "regionIds": [],
                "players": 0,
            },
        )
        o["players"] += 1
        if j["scoutingRegionId"] and j["scoutingRegionId"] not in o["regionIds"]:
            o["regionIds"].append(j["scoutingRegionId"])

    return cast(
        dict[str, Any],
        {
            "scouts": sorted(ojeadores.values(), key=lambda o: -o["players"]),
            "players": jugadores,
        },
    )


@router.get(
    "/teams/{team_id}/academy/skill-scores",
    summary="Qué entrenar, con los parámetros que elija el usuario",
    dependencies=[Depends(require_team_owner)],
)
async def academy_skill_scores(
    team_id: int,
    soon_max_days: int = Query(
        yss.SOON_MAX_DAYS,
        ge=0,
        le=112,
        description="Los días del corte: sale joven quien lo hace con menos de 17;<este número>",
    ),
    weight_base: float = Query(
        yss.DEFAULT_WEIGHT_BASE,
        ge=yss.MIN_WEIGHT_BASE,
        le=yss.MAX_WEIGHT_BASE,
        description="Cuánto separa un peldaño del siguiente; 3 son los pesos originales",
    ),
    trainable_method: str = Query(
        yss.TrainableMethod.EDIT,
        description=(
            "De dónde sale el conteo de «entrenables»: attack / midfield / defence "
            "(aporte de la habilidad a ese bloque), senior (lo que entrena el primer "
            "equipo, 16 contra 0) o edit (a mano)"
        ),
    ),
    trainable_weight: float | None = Query(
        None,
        ge=0,
        le=100,
        description=(
            "Peso del bonus personalizado. Si no se manda, lo sugiere la escalera "
            "(el peldaño -2 de la base)"
        ),
    ),
    trainable: str = Query(
        "",
        description=(
            "Cuántos canteranos reciben cada entrenamiento, como «habilidad:n» separado por comas"
        ),
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Recalcula el ranking sin tocar el método.

    Los tres parámetros son opiniones, no hechos: dónde cae el corte del
    plazo, cuánto pesa un peldaño sobre el de abajo, y a cuántos les llega de
    verdad cada entrenamiento. El resto —la nota por habilidad, los cubos, la
    escalera— es la metodología y no se negocia desde la URL.
    """
    counts: dict[str, float] = {}
    for chunk in trainable.split(","):
        skill, _, raw = chunk.partition(":")
        skill = skill.strip()
        if skill not in yss.SKILLS:
            continue
        try:
            valor = float(raw)
        except ValueError:
            continue
        # Un negativo restaría puntaje, que no significa nada: nadie puede
        # recibir menos de cero entrenamientos.
        counts[skill] = max(0.0, min(valor, float(yss.SQUAD_NORMALISER)))

    if trainable_method not in set(yss.TrainableMethod):
        raise HTTPException(422, f"método de entrenables desconocido: {trainable_method}")
    service = AcademyQueryService(session)
    counts = await service.trainable_by_method(team_id, trainable_method, counts)

    rows = await service.skill_scores(
        team_id,
        soon_max_days=soon_max_days,
        weight_base=weight_base,
        trainable_weight=trainable_weight,
        trainable=counts,
    )
    if rows is None:
        raise HTTPException(404, f"team {team_id} sin canteranos")
    return cast(
        dict[str, Any],
        _camel(
            {
                "soonMaxDays": soon_max_days,
                "weightBase": weight_base,
                "trainableMethod": trainable_method,
                # Los pesos que salen de la base, para pintarlos sobre cada columna:
                # el usuario juega con potencias y quiere verlas, no deducirlas.
                "weights": yss.weights_for(weight_base),
                # El sugerido por la escalera y el que de verdad se usó: la pantalla
                # enseña el primero como propuesta y el segundo como valor del mando.
                "suggestedTrainableWeight": yss.trainable_weight_for(weight_base),
                # Las plazas que entrena cada cosa, para que «Editar a mano» arranque
                # de la verdad en vez de ceros: el usuario ajusta, no teclea de cero
                # unos numeros que la aplicacion ya sabe.
                "slotCounts": yss.slot_trainable(),
                "trainableWeight": (
                    yss.trainable_weight_for(weight_base)
                    if trainable_weight is None
                    else trainable_weight
                ),
                # La pareja sugerida: la habilidad que mas puntua y, de la segunda,
                # la FORMA que mas solapa con la primera. Sin eso, «Defensa + Pases»
                # se lee como una recomendacion util cuando en realidad no dejaria a
                # nadie recibiendo las dos cosas.
                "suggestion": _pareja_sugerida(rows),
                # Todos los entrenamientos, variantes incluidas: son las opciones
                # reales de los dos selectores. Antes solo se ofrecian las siete
                # habilidades, asi que «Pases (defensas y centro del campo completo)»
                # no se podia elegir aunque la sugerencia la recomendara.
                "trainings": [
                    {"code": e.codigo, "label": e.label, "skill": e.skill}
                    for e in ENTRENAMIENTOS.values()
                ],
                "skillScores": [asdict(r) for r in rows],
            }
        ),
    )
