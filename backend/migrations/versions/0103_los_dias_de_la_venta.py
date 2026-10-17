"""Los días de la edad del vendido, para el tope de los 17 años.

2026-10-17. Sondeando el Comparador de Transferencias se vio que a los 17 años
--y sólo a esa edad-- Hattrick añade un criterio más: `Días <= 24`. Está medido
desde el 2026-10-10 y hasta hoy se calculaba, se probaba y nadie lo consumía,
porque hacía falta el dato y no lo guardábamos.

ES UNA CONSTANTE, no sale del jugador. El mismo perfil pedido desde dos fichas
con días distintos --29 años y 2 días, y 28 y 20-- devuelve el mismo 24. Así que
basta con saber los días del CANDIDATO; los del nuestro no hacen falta.

POR QUÉ UNA COLUMNA Y NO UN PARCHE. La búsqueda no lo necesita: `transfersearch`
acepta años y no días, así que le pedimos un superconjunto y eso no hace daño.
Donde importa es en el sello del 100 %, que comprueba la regla entera contra la
venta ya guardada. Si el tope se aplicara sólo a los candidatos vivos del
mercado --donde sí tenemos los días-- la MISMA venta tendría sello antes de
guardarse y lo perdería después. Una incoherencia que aparece y desaparece es
peor que una inexactitud constante, así que o se aplica en los dos sitios o en
ninguno, y para el guardado hace falta la columna.

MENOS UNO SIGNIFICA «NO LOS SABEMOS», no «cero días». Las ventas guardadas antes
de esta columna se quedan así y el tope no se les aplica: siguen midiéndose como
hasta ahora. No se borran ni se inventan, que es la misma decisión que se tomó
con `skills_json` en la 0102.

Y NO SE PUEDEN RELLENAR. Haría falta saber los días que tenía el vendido EL DÍA
DE LA VENTA, y eso CHPP no lo publica. Envejecen y se reemplazan solas según
entran ventas nuevas.

Revision ID: 0103
Revises: 0102
"""

import sqlalchemy as sa
from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_sales",
        sa.Column("age_days", sa.Integer(), nullable=False, server_default="-1"),
    )


def downgrade() -> None:
    op.drop_column("market_sales", "age_days")
