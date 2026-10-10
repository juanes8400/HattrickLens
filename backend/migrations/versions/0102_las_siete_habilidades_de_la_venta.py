"""Las siete habilidades del jugador vendido, no sólo las tres que cuentan.

2026-10-10. Se sondeó el Comparador de Transferencias del propio Hattrick --unas
600 consultas a su panel «Editar búsqueda»-- y resultó que su regla mira MÁS de
las tres habilidades principales: le da criterio propio a la cuarta cuando pasa
de cinco, y pone tope a las otras tres. Con la terna sola no se puede responder
a «¿esta venta se la habría enseñado Hattrick?», y responder a medias sería peor
que no responder: daría por bueno a un jugador que el juego descartaría por una
cuarta alta.

UNA COLUMNA JSON Y NO SIETE. Son un dato del momento en que se vio la venta, se
escriben una vez --un jugador vendido ya no cambia-- y nadie las va a consultar
por separado: quien las lee, las lee todas juntas para pasárselas a la regla.

LAS FILAS VIEJAS SE QUEDAN VACÍAS Y NO PASA NADA. `lo_ensenaria_hattrick`
devuelve falso cuando faltan, así que esas ventas siguen midiéndose con nuestra
escalera de siempre. No se borra ni se inventa nada: envejecen y se reemplazan
solas según entran ventas nuevas.

Revision ID: 0102
Revises: 0101
"""

import sqlalchemy as sa
from alembic import op

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_sales", sa.Column("skills_json", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("market_sales", "skills_json")
