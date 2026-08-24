"""Juveniles. HL-110, HL-111, HL-112, HL-114, HL-115."""
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.arena import _camel
from app.application.queries.academy import AcademyQueryService
from app.domain.engines import youth_skill_score as yss
from app.domain.engines.youth_training_plan import (
    ENTRENAMIENTOS,
    mejor_variante,
    youth_training_plan,
)
from app.api.deps import require_team_owner
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get("/teams/{team_id}/academy", summary="Canteranos, plazos y retorno de la academia",
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
        principal.skill, codigo, principal.players, segunda.players,
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
        "bothWeeks": plan.semanas_dobles,
    }


def _alternativas(main, por_habilidad, habilidad_de):
    """Cuantos recibirian doble racion con cada secundario posible."""
    salida = []
    for e in ENTRENAMIENTOS.values():
        skill_main, skill_sec = habilidad_de(main), e.skill
        if skill_main not in por_habilidad or skill_sec not in por_habilidad:
            continue
        plan = youth_training_plan(
            main, e.codigo,
            por_habilidad[skill_main].players,
            por_habilidad[skill_sec].players,
            tope_principal={p.name for p in por_habilidad[skill_main].at_max},
            tope_secundaria={p.name for p in por_habilidad[skill_sec].at_max},
        )
        salida.append({
            "code": e.codigo,
            "label": e.label,
            "bothCount": plan.con_doble,
            # Las semanas desempatan: dos alternativas pueden llegar a los
            # mismos cinco y repartirles plazos muy distintos.
            "bothWeeks": plan.semanas_dobles,
        })
    return salida


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
    campo. La intersección --los que reciben doble ración-- se llena primero
    con los mejores del principal; ver `youth_training_plan`.
    """
    for nombre, valor in (("main", main), ("secondary", secondary)):
        # Vale una habilidad a secas --«passing»-- o un entrenamiento concreto
        # --«passing_defenders»--: la sugerencia manda el segundo.
        if valor not in yss.SKILLS and valor not in ENTRENAMIENTOS:
            raise HTTPException(422, f"{nombre}: «{valor}» no es un entrenamiento")

    service = AcademyQueryService(session)
    rows = await service.skill_scores(
        team_id, soon_max_days=soon_max_days, weight_base=weight_base,
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
    mejores = {
        j.name: j.best_skill for j in (academia.players if academia else [])
    }

    plan = youth_training_plan(
        main, secondary,
        por_habilidad[skill_main].players,
        por_habilidad[skill_sec].players,
        tope_principal={p.name for p in por_habilidad[skill_main].at_max},
        tope_secundaria={p.name for p in por_habilidad[skill_sec].at_max},
    )
    etiquetas = {r.skill: r.label for r in rows}

    def etiqueta_de(clave: str, skill: str) -> str:
        e = ENTRENAMIENTOS.get(clave)
        return e.label if e else etiquetas.get(skill, skill)

    return cast(dict[str, Any], _camel({
        "main": main,
        "mainLabel": etiqueta_de(main, skill_main),
        "secondary": secondary,
        "secondaryLabel": etiqueta_de(secondary, skill_sec),
        "doubleCount": plan.con_doble,
        "doubleWeeks": plan.semanas_dobles,
        # Que pasaria con CADA alternativa de secundario, para poder elegir
        # sabiendo: el desplegable ensena el numero al lado de cada opcion en
        # vez de obligar a probarlas una por una.
        #
        # Se rehace el plan entero de cada alternativa en vez de medir el
        # solape de PUESTOS, que es otra cosa: un puesto de la interseccion
        # que nadie ocupa no es una racion doble, y el numero de la lista
        # tiene que ser el mismo que se vera al elegirla.
        "alternatives": _alternativas(main, por_habilidad, habilidad_de),
        "assignments": [asdict(a) for a in plan.asignaciones],
        # El banquillo: los que no entraron, con lo mismo que llevan los de
        # dentro y la columna en que caen. Un juvenil no tiene puesto asignado
        # en Hattrick, asi que la columna sale de la habilidad en la que mas
        # destaca --es una lectura nuestra, no un dato del juego.
        "outside": [
            {**asdict(a), "benchColumn": _columna_de_banquillo(mejores.get(a.player))}
            for a in plan.fuera
        ],
    }))


@router.get(
    "/teams/{team_id}/academy/skill-scores",
    summary="Qué entrenar, con los parámetros que elija el usuario",
    dependencies=[Depends(require_team_owner)],
)
async def academy_skill_scores(
    team_id: int,
    soon_max_days: int = Query(
        yss.SOON_MAX_DAYS, ge=0, le=112,
        description="Los días del corte: sale joven quien lo hace con menos de 17;<este número>",
    ),
    weight_base: float = Query(
        yss.DEFAULT_WEIGHT_BASE, ge=yss.MIN_WEIGHT_BASE, le=yss.MAX_WEIGHT_BASE,
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
        None, ge=0, le=100,
        description=(
            "Peso del bonus personalizado. Si no se manda, lo sugiere la escalera "
            "(el peldaño -2 de la base)"
        ),
    ),
    trainable: str = Query(
        "",
        description=(
            "Cuántos canteranos reciben cada entrenamiento, "
            "como «habilidad:n» separado por comas"
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
    return cast(dict[str, Any], _camel({
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
            yss.trainable_weight_for(weight_base) if trainable_weight is None
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
    }))
