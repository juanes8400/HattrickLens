"""Un punto por semana de Hattrick, y la venta cuenta en la semana que cerró.

2026-11-08, decisión del usuario, dicha en dos frases:

  «Todo lo que haya sido finalizado en la semana TT-ss pasa a ser parte del
  Promedio de la semana.»

  «A medida que pasa la semana, se pueden ir agregando los datos que van a
  participar del promedio semanal, luego la semana se cierra y ya no se
  movería.»

LO QUE HABÍA. Una fila por cada vez que el número CAMBIABA. Con el barrido
diario eso son varios puntos por semana, y el punto cae donde NOSOTROS nos
enteramos, no donde ocurrió la venta: una subasta que cierra el domingo a las
23:00 se resuelve el lunes, o sea en la semana siguiente, y su precio aparecía
una semana tarde. La gráfica dibujaba una semana plana donde sí había pasado
algo.

LO QUE HAY. Una fila por SEMANA DE HATTRICK y jugador. La semana en curso está
viva: cada venta que cierra y se resuelve la actualiza. Una semana pasada
puede todavía recibir una venta rezagada --la del domingo, resuelta el
lunes-- y por eso no se sella al terminar, sino cuando ya no le queda ninguna
venta sin resolver. Con dos comprobaciones eso son como mucho un par de días.
Después no se mueve nunca más.

`season_week` es la etiqueta «TT-ss» que ya calcula `season_week_for_datetime`
a partir del ancla de `worlddetails`. La semana de Hattrick resultó ser la
misma semana ISO que usan las gráficas de habilidad --las dos anclan en
`start_of_iso_week`-- así que no hace falta un calendario nuevo.

LA SERIE EMPIEZA LIMPIA (decisión suya el mismo día). Las filas viejas se
quedan con `season_week` vacía y dejan de dibujarse. No se borran: son lo
único que no se podría reconstruir, porque el fondo no sabe cómo estuvo. La
gráfica se queda casi vacía una temporada y crece de un punto por semana, y
él lo sabía al elegirlo.

Revision ID: 0113
Revises: 0112
"""

import sqlalchemy as sa
from alembic import op

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_estimates",
        sa.Column("season_week", sa.String(length=8), nullable=False, server_default=""),
    )
    # Buscar «la fila de este jugador para esta semana» es lo que hace el
    # barrido en cada pasada, una vez por jugador. Sin índice son 27 recorridos
    # de la tabla entera por sincronización.
    op.create_index(
        "ix_market_estimates_semana",
        "market_estimates",
        ["team_id", "ht_player_id", "season_week"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_estimates_semana", table_name="market_estimates")
    op.drop_column("market_estimates", "season_week")
