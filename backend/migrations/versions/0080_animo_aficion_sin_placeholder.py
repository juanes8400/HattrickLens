"""El -1 de la popularidad con la aficion tampoco es un nivel.

Mismo criterio que la 0078 para Espiritu y Confianza, extendido al tercer
indicador de animo: la popularidad con la aficion, que vive en economy.xml.

POR QUE, SI NUNCA SE HA VISTO UN -1. Porque es la misma clase de dato -- un
nivel en una escala -- y la misma clase de fallo. Se comprobaron las dos bases
antes de escribir esto: cero filas con -1 en local y cero en produccion, con
quince equipos y semanas de historial. El campo no se oculta durante los
partidos como los otros dos. Pero si algun dia llega, sin esta revision se
guardaria como un nivel y la afici0n apareceria odiandote en la grafica y en
Cambios (2026-09-02, pedido del usuario).

La columna pasa a admitir NULL. Las filas historicas NO se reescriben: no hay
ninguna que reescribir, y aunque la hubiera, cambiar solo la columna rompe la
correspondencia con su `content_hash` -- el mismo motivo que da la 0078.

Revision ID: 0080
Revises: 0079
"""

import sqlalchemy as sa
from alembic import op

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("economy_snapshots") as batch_op:
        batch_op.alter_column(
            "supporters_popularity",
            existing_type=sa.SmallInteger(),
            nullable=True,
        )


def downgrade() -> None:
    """Vuelve a exigir un valor.

    Un NULL no puede volver a ser -1 sin inventar un nivel que Hattrick nunca
    dijo, asi que primero se rellenan con la ultima lectura valida del mismo
    equipo; si un equipo no tuviera ninguna, con 0, que es el suelo de la
    escala. Es una perdida de informacion aceptada: bajar de revision no
    deberia hacer falta, y si se hace, la alternativa era no poder bajar.
    """
    op.execute(
        """
        UPDATE economy_snapshots AS e
        SET supporters_popularity = COALESCE(
            (
                SELECT p.supporters_popularity
                FROM economy_snapshots AS p
                WHERE p.team_id = e.team_id
                  AND p.supporters_popularity IS NOT NULL
                  AND p.captured_at <= e.captured_at
                ORDER BY p.captured_at DESC
                LIMIT 1
            ),
            0
        )
        WHERE e.supporters_popularity IS NULL
        """
    )
    with op.batch_alter_table("economy_snapshots") as batch_op:
        batch_op.alter_column(
            "supporters_popularity",
            existing_type=sa.SmallInteger(),
            nullable=False,
        )
