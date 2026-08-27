"""Regla de habilidad entrenada para jugadores vendidos."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.application.commands.backfill_sold_training import _skill_increases
from app.domain.engines.sold_training_assignment import (
    SoldPlayerEvidence,
    derive_training_assignments,
)


def evidence(
    stint_id: int,
    player_id: int,
    season: int,
    **increases: int,
) -> SoldPlayerEvidence:
    return SoldPlayerEvidence(
        stint_id=stint_id,
        player_id=player_id,
        sale_season=season,
        is_real_sale=True,
        increases=increases,
    )


def test_unique_positive_maximum_is_direct_assignment() -> None:
    assignments = derive_training_assignments(
        [evidence(1, 10, 84, passing=3, defending=1, scoring=0)]
    )

    assert assignments[1].skill == "passing"
    assert assignments[1].levels == 3
    assert assignments[1].method == "direct_maximum"


def test_ambiguous_player_uses_total_levels_of_sale_season_first() -> None:
    rows = [
        evidence(1, 10, 84, passing=3, defending=1),
        evidence(2, 20, 84, passing=2, defending=0),
        evidence(3, 30, 84, passing=1, defending=1),
        evidence(4, 40, 84, passing=0, defending=0),
        # Otra temporada nunca puede votar en la 84.
        evidence(5, 50, 83, scoring=8),
    ]

    assignments = derive_training_assignments(rows)

    assert assignments[3].skill == "passing"
    assert assignments[3].levels == 1
    assert assignments[3].method == "season_levels"
    assert assignments[4].skill == "passing"
    assert assignments[4].levels == 0
    assert assignments[4].method == "season_levels"


def test_levels_have_priority_over_number_of_players() -> None:
    assignments = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=4),
            evidence(2, 20, 84, defending=2),
            evidence(3, 30, 84, defending=1),
            evidence(4, 40, 84),
        ]
    )

    # Pases subió 4 niveles en una persona; Defensa, 3 niveles en dos.
    assert assignments[4].skill == "passing"
    assert assignments[4].method == "season_levels"


def test_number_of_players_breaks_a_tie_in_total_levels() -> None:
    assignments = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=4),
            evidence(2, 20, 84, defending=2),
            evidence(3, 30, 84, defending=2),
            evidence(4, 40, 84),
        ]
    )

    assert assignments[4].skill == "defending"
    assert assignments[4].method == "season_players"


def test_tied_players_prefers_current_training_when_it_is_a_candidate() -> None:
    assignments = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=2),
            evidence(2, 20, 84, defending=2),
            evidence(3, 30, 84, passing=1, defending=1),
        ],
        current_training_skill="passing",
    )

    assert assignments[3].skill == "passing"
    assert assignments[3].levels == 1
    assert assignments[3].method == "season_current_training"


def test_tied_players_use_fixed_priority_when_current_training_cannot_break_tie() -> None:
    assignments = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=2),
            evidence(2, 20, 84, defending=2),
            evidence(3, 30, 84, passing=1, defending=1),
        ],
        current_training_skill="scoring",
    )

    assert assignments[3].skill == "defending"
    assert assignments[3].levels == 1
    assert assignments[3].method == "season_skill_priority"


def test_fixed_priority_has_the_exact_requested_order() -> None:
    priority = [
        "defending",
        "keeper",
        "playmaking",
        "scoring",
        "winger",
        "passing",
        "set_pieces",
    ]
    for index, (preferred, secondary) in enumerate(
        zip(priority, priority[1:], strict=False),
        start=1,
    ):
        assignments = derive_training_assignments(
            [
                evidence(1, 10, 80 + index, **{preferred: 2}),
                evidence(2, 20, 80 + index, **{secondary: 2}),
                evidence(3, 30, 80 + index),
            ]
        )

        assert assignments[3].skill == preferred
        assert assignments[3].method == "season_skill_priority"


def test_zero_evidence_stays_unresolved_even_with_current_training() -> None:
    assignments = derive_training_assignments(
        [evidence(1, 10, 84), evidence(2, 20, 84)],
        current_training_skill="passing",
    )

    assert assignments[1].skill is None
    assert assignments[1].levels is None
    assert assignments[1].method == "insufficient_evidence"
    assert assignments[2].method == "insufficient_evidence"


def test_zero_evidence_does_not_fall_back_to_defending() -> None:
    assignments = derive_training_assignments(
        [evidence(1, 10, 84)],
        current_training_skill="stamina",
    )

    assert assignments[1].skill is None
    assert assignments[1].levels is None
    assert assignments[1].method == "insufficient_evidence"


def test_assignment_changes_when_new_higher_priority_evidence_arrives() -> None:
    ambiguous = evidence(3, 30, 84, passing=0, defending=0)
    initial = derive_training_assignments(
        [evidence(1, 10, 84, passing=2), evidence(2, 20, 84, passing=3), ambiguous]
    )
    assert initial[3].skill == "passing"

    changed = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=2),
            evidence(2, 20, 84, passing=3),
            evidence(4, 40, 84, defending=2),
            evidence(5, 50, 84, defending=4),
            evidence(6, 60, 84, defending=3),
            ambiguous,
        ]
    )
    assert changed[3].skill == "defending"
    assert changed[3].method == "season_levels"


def test_unique_level_total_replaces_a_previous_lower_priority_tiebreak() -> None:
    ambiguous = evidence(3, 30, 84)
    initial = derive_training_assignments(
        [evidence(1, 10, 84, passing=2), evidence(2, 20, 84, defending=2), ambiguous],
        current_training_skill="passing",
    )
    assert initial[3].skill == "passing"
    assert initial[3].method == "season_current_training"

    changed = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=2),
            evidence(2, 20, 84, defending=2),
            evidence(4, 40, 84, defending=3),
            ambiguous,
        ],
        current_training_skill="passing",
    )
    assert changed[3].skill == "defending"
    assert changed[3].method == "season_levels"


def test_same_player_votes_only_once_per_season() -> None:
    assignments = derive_training_assignments(
        [
            evidence(1, 10, 84, passing=2),
            evidence(2, 10, 84, passing=2),
            evidence(3, 20, 84, defending=3),
            evidence(4, 30, 84),
        ]
    )

    # Si el jugador 10 contara dos veces, Pases sumaría 4 y ganaría. Como su
    # tramo histórico no se duplica, Pases suma 2 y Defensa suma 3.
    assert assignments[4].skill == "defending"
    assert assignments[4].method == "season_levels"


def test_fired_players_are_not_assigned_or_used_as_donors() -> None:
    fired = SoldPlayerEvidence(
        stint_id=1,
        player_id=10,
        sale_season=84,
        is_real_sale=False,
        increases={"passing": 9},
    )
    ambiguous_sale = evidence(2, 20, 84, passing=0)

    assignments = derive_training_assignments(
        [fired, ambiguous_sale],
        current_training_skill="passing",
    )

    assert assignments[1].method == "insufficient_evidence"
    assert assignments[2].method == "insufficient_evidence"


def test_snapshot_difference_is_last_before_sale_minus_first_ever() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    sale = started + timedelta(days=30)
    snapshots = [
        SimpleNamespace(captured_at=started, passing=4, defending=5),
        SimpleNamespace(captured_at=started + timedelta(days=20), passing=7, defending=6),
        # La lectura posterior a la venta no puede modificar la asignación.
        SimpleNamespace(captured_at=started + timedelta(days=40), passing=7, defending=12),
    ]
    for snapshot in snapshots:
        for skill in ("keeper", "playmaking", "winger", "scoring", "set_pieces"):
            setattr(snapshot, skill, 0)

    increases = _skill_increases(snapshots, sale)  # type: ignore[arg-type]

    assert increases["passing"] == 3
    assert increases["defending"] == 1
