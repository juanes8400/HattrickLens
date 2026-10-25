"""Los reportes de fallos, dichos desde dentro de la aplicación.

2026-10-25, cerrando un reporte de usuario que terminaba así: «By the way, I
didn't see any "report bug" or such button on the site itself». No lo había.

POR QUÉ UNA TABLA Y NO UN ENLACE A GITHUB. El repositorio es público y tiene
las incidencias abiertas, así que un enlace habría costado cero. Pero quien
reporta esto es un MANAGER DE HATTRICK, no un programador: mandarlo a abrirse
una cuenta en GitHub para contar que el sincronizador se le corta es casi no
darle el botón. Y encaja con cómo está hecho el resto --el uso se mide en el
propio servidor, sin servicios de terceros--, así que un reporte tampoco tiene
por qué salir de aquí.

QUÉ SE GUARDA Y QUÉ NO. El texto, quién lo escribe, cuándo, y desde qué
pantalla. La pantalla va porque es el dato que más veces falta en un reporte y
el único que se puede rellenar solo. El navegador va porque media docena de
fallos de esta aplicación han sido de un navegador concreto.

NO se guarda nada que el usuario no haya escrito: ni su correo, ni su IP, ni
nada de la sesión. Si hace falta contestarle, se le escribe por Hattrick, que
es donde ya se le conoce.

`atendido` no es un estado con flujo: es un sí o un no para que la lista de
pendientes no haya que llevarla en la cabeza.

Revision ID: 0104
Revises: 0103
"""

import sqlalchemy as sa
from alembic import op

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bug_reports",
        # LA MISMA VARIANTE QUE `PKBigInt` EN LOS MODELOS, y no un `BigInteger`
        # a secas. SQLite sólo trata como autoincremental la columna declarada
        # literalmente `INTEGER PRIMARY KEY`: con `BIGINT PRIMARY KEY` el
        # insert falla con «NOT NULL constraint failed». Se vio probándolo en
        # el navegador, no en las pruebas --las pruebas montan las tablas con
        # `create_all`, que usa los modelos y por tanto la variante correcta,
        # así que este fallo sólo aparece sobre una base migrada--.
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("at", sa.DateTime(), nullable=False, index=True),
        # La pantalla desde la que se escribió, rellenada sola.
        sa.Column("module", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False),
        # Qué navegador, que es de donde salen la mitad de los fallos de esta
        # aplicación. Recortado: la cadena entera no aporta más.
        sa.Column("user_agent", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("atendido", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("bug_reports")
