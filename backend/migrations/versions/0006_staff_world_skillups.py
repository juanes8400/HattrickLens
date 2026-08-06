"""Staff, contexto del mundo y subidas de habilidad confirmadas.

Cierra la fórmula de entrenamiento: `staff_snapshots.assistant_trainer_levels`
es el nivel de ayudantes leído de CHPP (club.AssistantTrainerLevels), no
supuesto; `world_context` trae la tasa de moneda y la temporada/jornada reales;
`skill_ups` guarda los pops que Hattrick confirma (trainingevents), con los que
se calibra la experiencia sin inferir nada.

Revision ID: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("sync_id", sa.BigInteger, sa.ForeignKey("syncs.id"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assistant_trainer_levels", sa.SmallInteger, server_default="0"),
        sa.Column("form_coach_levels", sa.SmallInteger, server_default="0"),
        sa.Column("medic_levels", sa.SmallInteger, server_default="0"),
        sa.Column("sport_psychologist_levels", sa.SmallInteger, server_default="0"),
        sa.Column("tactical_assistant_levels", sa.SmallInteger, server_default="0"),
        sa.Column("financial_director_levels", sa.SmallInteger, server_default="0"),
        sa.Column("spokesperson_levels", sa.SmallInteger, server_default="0"),
        sa.Column("trainer_skill_level", sa.SmallInteger, server_default="0"),
        sa.Column("trainer_type", sa.SmallInteger, server_default="2"),
        sa.Column("trainer_leadership", sa.SmallInteger, server_default="0"),
        sa.Column("youth_investment", sa.Integer, server_default="0"),
        sa.Column("youth_level", sa.SmallInteger, server_default="0"),
        sa.Column("content_hash", sa.LargeBinary(32), nullable=False),
    )
    op.create_index("ix_staff_team_time", "staff_snapshots", ["team_id", "captured_at"])

    op.create_table(
        "world_context",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ht_league_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("league_name", sa.String(128), server_default=""),
        sa.Column("season", sa.SmallInteger, server_default="0"),
        sa.Column("match_round", sa.SmallInteger, server_default="0"),
        sa.Column("match_rounds_left", sa.SmallInteger, server_default="0"),
        sa.Column("number_of_levels", sa.SmallInteger, server_default="0"),
        sa.Column("currency_name", sa.String(16), server_default=""),
        sa.Column("currency_rate", sa.Float, server_default="1.0"),
        sa.Column("training_date", sa.DateTime(timezone=True)),
        sa.Column("series_match_date", sa.DateTime(timezone=True)),
        sa.Column("refreshed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "skill_ups",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("ht_player_id", sa.BigInteger, nullable=False),
        sa.Column("skill_id", sa.SmallInteger, nullable=False),
        sa.Column("old_level", sa.SmallInteger, nullable=False),
        sa.Column("new_level", sa.SmallInteger, nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("match_round", sa.SmallInteger, nullable=False),
        sa.Column("day_number", sa.SmallInteger, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_skillup_team", "skill_ups", ["team_id"])
    op.create_index("ix_skillup_player", "skill_ups", ["ht_player_id"])
    op.create_index(
        "ix_skillup_unique", "skill_ups",
        ["ht_player_id", "skill_id", "new_level"], unique=True,
    )


def downgrade() -> None:
    op.drop_table("skill_ups")
    op.drop_table("world_context")
    op.drop_index("ix_staff_team_time", table_name="staff_snapshots")
    op.drop_table("staff_snapshots")
