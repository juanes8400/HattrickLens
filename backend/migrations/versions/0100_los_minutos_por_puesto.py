"""Lo que paso despues del pitido inicial: los cambios y el cobrador.

2026-10-08, reportado por un usuario: su jugador 513909842 jugo 87 minutos de
lateral y 3 de extremo, y HT Lens le daba la semana entera de entrenamiento de
Lateral, el 100 %. Le tocaba el 51,7 %, porque el lateral cobra el 50 %.

POR QUE NO SE PODIA CALCULAR. Los minutos salian de `playerdetails.xml`, que en
`<LastMatch>` publica UN `PositionCode` --el puesto en el que el jugador
acabo-- y el TOTAL de `PlayedMinutes`. Una sola fila por partido, con el
indice unico `ix_pmr_player_match` encima. Un jugador que cambia de puesto
llega como «extremo, 90 minutos» y no hay nada que repartir.

DE DONDE SALE AHORA. De `matchlineup.xml` 2.1, el mismo fichero del que ya se
sacaba el once inicial, en la misma peticion: `<Substitutions>` trae cada orden
con su `MatchMinute`, quien sale, quien entra y `NewPositionId`. Hasta hoy se
leia y se tiraba.

Y DE PASO, EL COBRADOR DE TIROS LIBRES. Viene en `<StartingLineup>` como una
fila mas del mismo jugador, con RoleID 17, y la sincronizacion lo descartaba
con el resto de papeles especiales. Hace falta porque en el entrenamiento de
Balon parado el cobrador recibe el 125 % juegue donde juegue (regla del
usuario, 2026-10-09).

Una columna y no una tabla: es un dato por partido, se escribe una sola vez
--un partido jugado no cambia-- y quien lo lee ya tiene el partido delante.

Revision ID: 0100
Revises: 0099
"""

import sqlalchemy as sa
from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("played_events_json", sa.String(length=4000), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "played_events_json")
