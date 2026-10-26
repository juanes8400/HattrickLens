"""Con qué criterios se midió cada punto de la serie de precios.

2026-10-26, decisión del usuario: cuando a un jugador le cambian los criterios
de comparación, «la gráfica de precios volverá a empezar».

POR QUÉ. Los criterios son del jugador y Hattrick los recalcula con él: al
cumplir años cambia su ventana de edad, y al subir una habilidad cambia cuál lo
identifica y con qué banda. Desde ese momento el barrido pregunta por OTRA
gente, así que el número de antes y el de después no son la misma medida.
Unirlos con una línea sería dibujar una subida o una bajada que no ocurrió.

NO SE BORRA NADA, y esto es una decisión y conviene que esté dicha. «Volver a
empezar» se podía leer como tirar los puntos viejos, y no se hace: la tabla
existe justamente porque el fondo no sabe cómo estuvo --al resolver una venta su
puja se pisa con el precio de cierre y el valor anterior desaparece-- así que
borrar la serie es la única pérdida de esta base que no se puede deshacer. Lo
que se hace es MARCAR cada punto con su clave; la pantalla enseña el tramo
vigente, que es lo que se pidió, y los tramos anteriores siguen ahí.

LAS FILAS DE ANTES SE QUEDAN SIN CLAVE, con la cadena vacía, y está bien: la
vacía no coincide con ninguna ventana, así que el primer punto que se anote tras
esta migración abre tramo. Rellenarlas habría que hacerlo adivinando qué
habilidades tenía el jugador aquel día, y adivinar en una serie histórica es
peor que empezar limpio.

Revision ID: 0107
Revises: 0106
"""

import sqlalchemy as sa
from alembic import op

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_estimates",
        sa.Column("criteria_key", sa.String(length=120), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("market_estimates", "criteria_key")
