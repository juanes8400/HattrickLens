"""El plazo de la subasta de un ex-jugador que vimos en el mercado.

2026-11-03, pedido por el usuario. La caza de comisiones de reventa trabaja a
ciegas: `economy.xml` dice que entró dinero de comisión, pero no de quién, y
hay 501 ex-jugadores en la cola. Se miran unos pocos por sincronización --uno
reciente, uno al azar-- y la mayoría de las llamadas se gastan en semanas
donde no había nada que encontrar.

`currentbids.xml` ya se descarga en cada sync y trae la lista de pujas en las
que andamos metidos. Entre ellas aparecen ex-jugadores nuestros que estamos
intentando recomprar, y ésa es la pista que faltaba: un ex-jugador EN EL
MERCADO es una reventa con fecha y hora. Quien lo esté vendiendo es el club al
que se lo vendimos, y de esa venta nos toca comisión de club anterior.

POR QUÉ SE GUARDA EL PLAZO Y NO UN «SÍ». Mirar antes de que cierre la subasta
no sirve: la reventa todavía no ha pasado. Con la fecha, la pista sabe cuándo
está madura, y ese momento es el mismo se venda o no se venda --que es lo que
el usuario pidió-- porque las dos cosas se resuelven al cerrar el plazo.

SE BORRA AL MIRARLO, en `_backfill_sold_player_details`. Una pista que no se
consume se queda para siempre a la cabeza de la cola y le roba el turno a los
otros 500.

Revision ID: 0110
Revises: 0109
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("resale_deadline", UtcDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "resale_deadline")
