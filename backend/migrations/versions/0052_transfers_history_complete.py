"""Saber si la historia de transferencias se recorrió ENTERA alguna vez.

2026-08-21, con la app publicada. Un usuario estrenando la herramienta abría
Transferencias y la veía vacía salvo una operación reciente, y volver a pulsar
el botón no arreglaba nada.

El primer intento se había cortado a la mitad (un error de fechas al comparar
con Postgres), pero la marca de agua `last_transfer_id_seen` se guardaba de
todas formas, apuntando a la transferencia más reciente. A partir de ahí, cada
intento nuevo leía la primera página, reconocía esa marca y concluía que ya
estaba todo al día — el hueco de temporadas anteriores no se rellenaba jamás.

La marca sola no distingue "he visto todo hasta aquí" de "me quedé aquí". Esta
bandera es esa diferencia, y solo se pone cuando el recorrido llega al final
sin errores. Mientras sea falsa, la marca se ignora y se empieza de cero, así
que los equipos que ya quedaron a medias se arreglan solos al siguiente clic.

Revision ID: 0052
"""
import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "transfers_history_complete",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("teams", "transfers_history_complete")
