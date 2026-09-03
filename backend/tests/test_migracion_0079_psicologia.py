"""La limpieza historica elimina placeholders sin inventar cambios."""

import importlib.util
import json
from datetime import datetime
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa


def _migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0079_limpiar_psicologia_historica.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0079", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_is_independent_exact_and_idempotent() -> None:
    migration = _migration()
    metadata = sa.MetaData()
    teams = sa.Table(
        "teams",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ht_team_id", sa.Integer, nullable=False),
    )
    snapshots = sa.Table(
        "training_snapshots",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sync_id", sa.Integer, nullable=False),
        sa.Column("team_id", sa.Integer, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
        sa.Column("training_type", sa.Integer, nullable=False),
        sa.Column("training_level", sa.Integer, nullable=False),
        sa.Column("new_training_level", sa.Integer, nullable=False),
        sa.Column("stamina_part", sa.Integer, nullable=False),
        sa.Column("last_training_type", sa.Integer, nullable=False),
        sa.Column("last_training_level", sa.Integer, nullable=False),
        sa.Column("last_stamina_part", sa.Integer, nullable=False),
        sa.Column("trainer_ht_id", sa.Integer, nullable=False),
        sa.Column("trainer_name", sa.String, nullable=False),
        sa.Column("morale", sa.Integer),
        sa.Column("self_confidence", sa.Integer),
        sa.Column("formation_xp_json", sa.String),
        sa.Column("content_hash", sa.LargeBinary, nullable=False),
    )
    changes = sa.Table(
        "sync_changes",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sync_id", sa.Integer, nullable=False),
        sa.Column("team_id", sa.Integer, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("summary", sa.String, nullable=False),
        sa.Column("detail_json", sa.String),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    base = {
        "training_type": 8,
        "training_level": 100,
        "new_training_level": 100,
        "stamina_part": 15,
        "last_training_type": 8,
        "last_training_level": 100,
        "last_stamina_part": 15,
        "trainer_ht_id": 99,
        "trainer_name": "Entrenador",
        "formation_xp": {"442": 7},
    }

    def snapshot(
        row_id: int,
        team_id: int,
        ht_team_id: int,
        morale: int,
        confidence: int,
    ) -> dict[str, object]:
        payload = {
            "ht_team_id": ht_team_id,
            **base,
            "morale": morale,
            "self_confidence": confidence,
        }
        return {
            "id": row_id,
            "sync_id": row_id,
            "team_id": team_id,
            # Un `datetime` de verdad, no su texto: el conector de SQLite
            # rechaza la cadena y la prueba entera reventaba al insertar.
            "captured_at": datetime(2026, 9, row_id, 12, 0),
            **{key: base[key] for key in base if key != "formation_xp"},
            "morale": morale,
            "self_confidence": confidence,
            "formation_xp_json": json.dumps(base["formation_xp"]),
            "content_hash": migration._hash(payload),
        }

    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            teams.insert(),
            [{"id": 1, "ht_team_id": 1001}, {"id": 2, "ht_team_id": 2002}],
        )
        connection.execute(
            snapshots.insert(),
            [
                snapshot(1, 1, 1001, -1, -1),
                snapshot(2, 1, 1001, 6, -1),
                snapshot(3, 1, 1001, -1, 5),
                snapshot(4, 1, 1001, -1, 6),
                snapshot(5, 1, 1001, 5, -1),
                snapshot(6, 2, 2002, 0, 0),
                snapshot(7, 2, 2002, -1, -1),
            ],
        )
        connection.execute(
            changes.insert(),
            [
                {
                    "sync_id": 4,
                    "team_id": 1,
                    "category": "entrenamiento",
                    "summary": "Confianza: -1 -> Alta",
                    "created_at": datetime(2026, 9, 4, 12, 0),
                },
                {
                    "sync_id": 4,
                    "team_id": 1,
                    "category": "entrenamiento",
                    "summary": "Confianza: Sólida -> Alta",
                    "created_at": datetime(2026, 9, 4, 12, 0),
                },
                {
                    "sync_id": 4,
                    "team_id": 1,
                    "category": "entrenamiento",
                    "summary": "Espíritu del equipo: -1 -> Contentos",
                    "created_at": datetime(2026, 9, 4, 12, 0),
                },
                {
                    "sync_id": 5,
                    "team_id": 1,
                    "category": "entrenamiento",
                    "summary": "Espíritu del equipo: -1 -> Calmados",
                    "created_at": datetime(2026, 9, 5, 12, 0),
                },
                {
                    "sync_id": 5,
                    "team_id": 1,
                    "category": "entrenamiento",
                    "summary": "Intensidad: 90 -> 100",
                    "created_at": datetime(2026, 9, 5, 12, 0),
                },
            ],
        )

        migration._clean_history(connection)
        cleaned = list(
            connection.execute(
                sa.select(
                    snapshots.c.id,
                    snapshots.c.morale,
                    snapshots.c.self_confidence,
                ).order_by(snapshots.c.id)
            ).tuples()
        )
        summaries = list(connection.scalars(sa.select(changes.c.summary).order_by(changes.c.id)))
        before_second_run = list(connection.execute(sa.select(changes)).tuples())
        migration._clean_history(connection)
        after_second_run = list(connection.execute(sa.select(changes)).tuples())

    assert cleaned == [
        (1, None, None),
        (2, 6, None),
        (3, 6, 5),
        (4, 6, 6),
        (5, 5, 6),
        (6, 0, 0),
        (7, 0, 0),
    ]
    assert not any("-1" in summary for summary in summaries)
    assert summaries.count("Confianza: Sólida -> Alta") == 1
    assert summaries.count("Espíritu del equipo: Contentos -> Calmados") == 1
    assert "Intensidad: 90 -> 100" in summaries
    assert before_second_run == after_second_run
