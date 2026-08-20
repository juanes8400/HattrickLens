"""Días que faltan para poder promocionar a un juvenil.

`CanBePromotedIn` de youthplayerlist.xml se parseaba y se tiraba. Es lo que
fija la "edad al salir" con la que la academia decide a quién le da tiempo de
entrenar: no es lo mismo un chico que se podrá promocionar en seis días que
uno al que le faltan noventa.

Ojo, NO es el plazo de `academy_engine.days_until_deadline`, que cuenta lo que
falta para cumplir 19 y perderlo. Son dos relojes distintos.

Revision ID: 0050
Revises: 0049
"""
import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: de los snapshots ya guardados no se sabe, y un 0 diría "se
    # puede promocionar ya", que es una afirmación y no una ausencia.
    op.add_column(
        "youth_snapshots",
        sa.Column("can_be_promoted_in", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("youth_snapshots", "can_be_promoted_in")
