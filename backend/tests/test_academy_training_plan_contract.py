"""Contrato del reparto juvenil: el castigo no puede perderse al serializar.

El motor ya comprobaba algunas raciones, pero el fallo real vivía después:
`/academy/training-plan` volvía a decidir la penalización línea por línea y
podía entregar 50 aunque el plan hubiese calculado otra cosa.
"""

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.api.v1.endpoints import academy as endpoint
from app.domain.engines import youth_skill_score as yss


def _fixture() -> tuple[list[Any], Any]:
    rows: list[Any] = []
    readings: list[Any] = []
    for skill in yss.SKILLS:
        note = yss.PlayerNote(
            name="Canterano Prueba",
            note=8,
            bucket="excelente",
            leaves_soon=False,
            max_reached=False,
            priority=1,
        )
        rows.append(
            SimpleNamespace(
                skill=skill,
                label=skill,
                score=1.0,
                counts={},
                trainable_count=1.0,
                players=[note],
                at_max=[],
            )
        )
        readings.append(
            SimpleNamespace(
                skill=skill,
                current=None,
                maximum=None,
                is_current_known=False,
                max_reached=False,
            )
        )
    academy = SimpleNamespace(
        players=[
            SimpleNamespace(
                name="Canterano Prueba",
                best_skill="winger",
                skills=readings,
            )
        ]
    )
    return rows, academy


def _plan(monkeypatch: pytest.MonkeyPatch, main: str, secondary: str) -> dict[str, Any]:
    rows, academy = _fixture()

    class FakeAcademyQueryService:
        def __init__(self, _session: Any) -> None:
            pass

        async def skill_scores(self, _team_id: int, **_params: Any) -> list[Any]:
            return rows

        async def get(self, _team_id: int) -> Any:
            return academy

    monkeypatch.setattr(endpoint, "AcademyQueryService", FakeAcademyQueryService)
    return asyncio.run(
        endpoint.academy_training_plan(
            team_id=1,
            main=main,
            secondary=secondary,
            soon_max_days=yss.SOON_MAX_DAYS,
            weight_base=yss.DEFAULT_WEIGHT_BASE,
            session=cast(Any, object()),
        )
    )


def test_pases_repetido_publica_100_mas_33_3(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _plan(monkeypatch, "passing", "passing")

    assert result["repeatedTraining"] is True
    assert result["secondaryFactor"] == pytest.approx(1 / 3)
    assert result["combinedFactor"] == pytest.approx(4 / 3)
    assignment = result["assignments"][0]
    assert assignment["racionPrincipal"] == 100
    assert assignment["racionSecundaria"] == pytest.approx(33.3)
    assert assignment["secondaryLines"][0]["rate"] == pytest.approx(33.3)
    assert assignment["secondaryLines"][0]["penalty"] == pytest.approx(1 / 3, abs=0.0001)


def test_individual_repetido_aplica_un_tercio_a_cada_salida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _plan(monkeypatch, "individual", "individual")

    assert result["repeatedTraining"] is True
    lines = result["assignments"][0]["secondaryLines"]
    assert lines
    assert all(line["penalty"] == pytest.approx(1 / 3, abs=0.0001) for line in lines)
    assert all(line["rate"] == pytest.approx(round(line["base"] / 3, 1)) for line in lines)


def test_lateral_mas_individual_no_castiga_la_salida_lateral_como_repetida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _plan(monkeypatch, "winger", "individual")

    assert result["repeatedTraining"] is False
    assert result["secondaryFactor"] == pytest.approx(2 / 3)
    winger = next(a for a in result["assignments"] if a["puesto"] == "winger")
    lateral = next(line for line in winger["secondaryLines"] if line["skill"] == "winger")
    assert lateral["base"] == 42.5
    assert lateral["rate"] == pytest.approx(28.3)
    assert lateral["penalty"] == pytest.approx(2 / 3, abs=0.0001)


def test_dos_entrenamientos_distintos_de_pases_conservan_dos_tercios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _plan(monkeypatch, "passing", "passing_defenders")

    assert result["repeatedTraining"] is False
    assert result["secondaryFactor"] == pytest.approx(2 / 3)
    midfielder = next(a for a in result["assignments"] if a["puesto"] == "inner_midfield")
    assert midfielder["racionPrincipal"] == 100
    assert midfielder["racionSecundaria"] == pytest.approx(53.3)

