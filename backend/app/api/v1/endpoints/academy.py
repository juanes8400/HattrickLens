"""Juveniles. HL-110, HL-111, HL-112, HL-114, HL-115."""
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.arena import _camel
from app.application.queries.academy import AcademyQueryService
from app.domain.engines import youth_skill_score as yss
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


@router.get(
    "/teams/{team_id}/academy/skill-scores",
    summary="Qué entrenar, con los parámetros que elija el usuario",
    dependencies=[Depends(require_team_owner)],
)
async def academy_skill_scores(
    team_id: int,
    soon_max_days: int = Query(
        yss.SOON_MAX_DAYS, ge=0, le=112,
        description="Hasta cuántos días para poder promocionar cuenta como «sale pronto»",
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
        "trainableWeight": (
            yss.trainable_weight_for(weight_base) if trainable_weight is None
            else trainable_weight
        ),
        "skillScores": [asdict(r) for r in rows],
    }))
