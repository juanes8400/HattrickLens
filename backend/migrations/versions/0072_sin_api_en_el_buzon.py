"""Borrar del buzon de alertas toda mencion a la API.

2026-08-31, orden del usuario: ninguna referencia a CHPP puede llegar a la
pantalla. El codigo quedo limpio, pero el buzon no: al archivar una alerta se
guarda su TEXTO tal como estaba en ese momento --es una huella de contenido, no
un puntero a la regla-- asi que las frases viejas siguen a la vista aunque
nadie las genere ya. En la base real quedaba una: "El nivel de psicologo
deportivo reportado por CHPP es 0.".

La huella se recalcula junto con el texto. Si no, la alerta reaparece como
nueva la proxima vez que se cumpla: el buzon la compara por hash de
severidad+titulo+detalle+accion, y cambiar el detalle sin tocar el hash la
volveria irreconocible para el filtro. Archivar es acusar recibo de un hecho,
y el hecho no ha cambiado por reescribir la frase.

Revision ID: 0072
Revises: 0071
"""

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


#: Las frases que se generaban antes, con su version limpia. Se reescribe por
#: coincidencia exacta: una sustitucion suelta de "CHPP" dejaria gramatica
#: rota ("reportado por es 0").
REESCRITURAS = {
    "El nivel de médico reportado por CHPP es 0.": (
        "El nivel de médico que reporta Hattrick es 0."
    ),
    "El nivel de psicólogo deportivo reportado por CHPP es 0.": (
        "El nivel de psicólogo deportivo que reporta Hattrick es 0."
    ),
}


def _huella(severity: str, title: str, detail: str, action: str) -> str:
    """La misma huella que calcula el endpoint. Se copia a proposito: una
    migracion tiene que seguir corriendo igual dentro de un año, aunque el
    endpoint se mueva de sitio."""
    return hashlib.sha256(
        "|".join((severity, title, detail, action)).encode("utf-8")
    ).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    tabla = sa.table(
        "dismissed_insights",
        sa.column("id", sa.Integer),
        sa.column("severity", sa.String),
        sa.column("title", sa.String),
        sa.column("detail", sa.String),
        sa.column("action", sa.String),
        sa.column("fingerprint", sa.String),
    )
    filas = conn.execute(
        sa.select(
            tabla.c.id, tabla.c.severity, tabla.c.title, tabla.c.detail, tabla.c.action
        )
    ).all()

    for fila in filas:
        detalle = REESCRITURAS.get(fila.detail or "")
        if detalle is None:
            continue
        conn.execute(
            tabla.update()
            .where(tabla.c.id == fila.id)
            .values(
                detail=detalle,
                fingerprint=_huella(
                    fila.severity or "", fila.title or "", detalle, fila.action or ""
                ),
            )
        )


def downgrade() -> None:
    """No se deshace: devolver la mencion a la API a la pantalla es justo lo
    que esta migracion existe para impedir."""
