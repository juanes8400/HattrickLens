"""is_home en match_ratings — HL-2xx, módulo de rivales.

Con datos reales de la cuenta se confirmó que en partidos NO oficiales
(Escaleras/Duelos, MatchType 50/62) `matchdetails.xml` reporta un TeamID
efímero para AMBOS lados del partido — ni siquiera el equipo propio conserva
su ht_team_id real ahí (ejemplo: partido 41857134 contra "Dinamo Boyacá",
ht_team_id real 1098294, pero las dos filas de match_ratings tienen
team_ht_id 823767 y 823774; el propio equipo, 537758, tampoco aparece).
`team_ht_id` es por tanto inútil para localizar la fila de un lado concreto
en esos partidos, tanto para el rival (módulo de rivales) como para el
equipo propio (página de detalle de partido).

La única señal fiable es la POSICIÓN en el XML: `_persist_match_details`
siempre inserta primero la fila `HomeTeam` y después `AwayTeam`
(`sync_team.py`, bucle `for side in ("home", "away")`), y esa posición SÍ
coincide siempre con `matches.Match.home_team_ht_id`/`away_team_ht_id`
(que vienen de `matches.xml`, un fichero distinto, y ahí sí son reales incluso
en Duelos — así es como la ficha de rival encuentra el partido en primer
lugar). El backfill se apoya en esa misma propiedad de inserción: para cada
`ht_match_id` existente, la fila con menor `id` es siempre la que se
insertó como "home" (verificado contra los 30 partidos ya sincronizados de la
cuenta de desarrollo, oficiales y no oficiales por igual — ninguna excepción).

Revision ID: 0018
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_ratings", sa.Column("is_home", sa.Boolean(), nullable=True))
    op.execute(
        "UPDATE match_ratings SET is_home = "
        "(id = (SELECT MIN(id) FROM match_ratings mr2 "
        "WHERE mr2.ht_match_id = match_ratings.ht_match_id))"
    )
    with op.batch_alter_table("match_ratings") as batch_op:
        batch_op.alter_column("is_home", nullable=False)


def downgrade() -> None:
    op.drop_column("match_ratings", "is_home")
