"""Una venta se identifica por SU SUBASTA, no por el jugador.

2026-10-26, preparando el barrido diario de precios. Decisión del usuario:
«Jugador + Plazo, aunque después haya transferID cuando se termina».

LO QUE HABÍA, y por qué deja de servir. La clave era `(equipo, jugador)`: si el
mismo jugador volvía a aparecer en el mercado, su fila se sobrescribía, con el
argumento de que «es otra venta, y la de antes ya cumplió su función». Con una
búsqueda semanal eso casi nunca pasaba y además era cómodo: un jugador, una
fila.

El barrido diario lo rompe por los dos lados a la vez:

· POR ARRIBA, un anuncio dura días, así que el mismo jugador con el mismo plazo
  va a aparecer siete días seguidos. Eso es UNA subasta vista siete veces, y
  con la clave nueva sigue siendo una fila.
· POR ABAJO, Hattrick SÍ cuenta dos ventas distintas del mismo jugador, y está
  medido: el 490357848 aparece en su propio Comparador dos veces, a 215.220 y a
  125.000 (AP14, 2026-10-11). Con la clave vieja la segunda borraba a la
  primera y perdíamos un comparable que el juego sí usa.

Jugador + plazo distingue las dos cosas de una vez, porque el plazo es un dato
de Hattrick que viene en el anuncio, no una estimación nuestra.

Y SIGUE SIENDO LA CLAVE DESPUÉS DE RESOLVERSE, aunque entonces ya tengamos el
`TransferID`, que sería un identificador mejor. No se cambia de clave a mitad:
el traspaso sólo existe cuando la subasta ya cerró, así que una clave basada en
él no podría identificar lo que todavía está en curso --que es justo lo que hay
que reconocer cada día para no duplicarlo--.

NO HACE FALTA TOCAR LOS DATOS. Las filas de antes siguen valiendo: cada una
tiene su plazo, así que ya cumplen la clave nueva. Lo único que cambia es que a
partir de ahora pueden tener hermanas.

Revision ID: 0105
Revises: 0104
"""

from alembic import op

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # En lote porque SQLite no sabe quitar una restricción: alembic rehace la
    # tabla. La base de desarrollo es SQLite y la de producción PostgreSQL, así
    # que esto tiene que valer en las dos.
    with op.batch_alter_table("market_sales") as batch:
        batch.drop_constraint("uq_market_sale_por_equipo", type_="unique")
        batch.create_unique_constraint(
            "uq_market_sale_por_subasta", ["team_id", "ht_player_id", "deadline"]
        )


def downgrade() -> None:
    # VOLVER ATRÁS PUEDE FALLAR, y es honesto que falle: si ya se guardaron dos
    # subastas del mismo jugador, la clave vieja no las admite. Quien necesite
    # bajar tendrá que decidir con cuál se queda; adivinarlo aquí sería tirar un
    # comparable sin preguntar.
    with op.batch_alter_table("market_sales") as batch:
        batch.drop_constraint("uq_market_sale_por_subasta", type_="unique")
        batch.create_unique_constraint(
            "uq_market_sale_por_equipo", ["team_id", "ht_player_id"]
        )
