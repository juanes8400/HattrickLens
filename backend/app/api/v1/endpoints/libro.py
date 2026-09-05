"""El libro de visitas.

2026-09-05, pedido por el usuario. Dos rutas: leer las firmas y dejar una.

Por qué pide sesión para firmar y no es anónimo: un libro abierto en internet
se llena de basura en un día, y moderar a mano lo que escribe cualquiera no es
trabajo que nadie vaya a hacer. Aquí para escribir hay que haber conectado con
Hattrick, así que detrás de cada firma hay un club de verdad.

Lo que se ENSEÑA es el nombre del club y el país, nunca el nombre de la
cuenta: en Hattrick uno se conoce por su equipo, y publicar el login de alguien
sería dar un dato que no hace falta para nada.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.api.rate_limit import limite
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

#: Cuántas firmas se devuelven de una tanda. El libro no es un foro: quien
#: llega quiere leer las últimas, no paginar cien.
POR_PAGINA = 50

#: Lo que cabe en una firma. Mil caracteres son unos tres párrafos: sitio de
#: sobra para contar qué te falta, y poco para convertir esto en un blog.
MAXIMO_DEL_MENSAJE = 1000


class FirmaEntrante(BaseModel):
    message: str = Field(min_length=1, max_length=MAXIMO_DEL_MENSAJE)


def _firma(fila: m.GuestbookEntry) -> dict[str, Any]:
    return {
        "id": fila.id,
        "teamName": fila.team_name,
        "country": fila.country,
        "message": fila.message,
        "createdAt": fila.created_at.isoformat(),
    }


@router.get("/guestbook", summary="Las firmas del libro de visitas")
async def leer(
    limit: int = Query(POR_PAGINA, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Las últimas firmas, de la más nueva a la más vieja.

    Las escondidas por moderación no salen. No se borran: ver el modelo.
    """
    filas = list(
        (
            await session.execute(
                select(m.GuestbookEntry)
                .where(m.GuestbookEntry.hidden.is_(False))
                .order_by(m.GuestbookEntry.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    return {"entries": [_firma(f) for f in filas]}


@router.post(
    "/guestbook",
    status_code=201,
    summary="Dejar una firma",
    # Cubo propio: agotar el libro no puede dejar a nadie sin sincronizar, y
    # al revés tampoco. Diez al día es de sobra para escribir de verdad y
    # poco para llenar la pantalla de alguien.
    dependencies=[Depends(limite("libro", 10))],
)
async def firmar(
    entrante: FirmaEntrante,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    mensaje = entrante.message.strip()
    if not mensaje:
        # Pydantic ya exige un carácter, pero un mensaje de sólo espacios lo
        # pasa y quedaría una firma en blanco en el libro.
        raise HTTPException(422, "el mensaje no puede estar vacío")

    # El club se copia AQUÍ, no se referencia: si mañana cambia de nombre, la
    # firma tiene que seguir diciendo cómo se llamaba al escribirla.
    equipo = await session.scalar(
        select(m.Team).where(m.Team.owner_user_id == user.id).order_by(m.Team.id).limit(1)
    )
    fila = m.GuestbookEntry(
        user_id=user.id,
        team_name=(equipo.name if equipo and equipo.name else ""),
        # La liga es lo que sitúa a alguien en Hattrick: «V.92 Colombia» dice
        # más que un país suelto, y es lo que la barra lateral ya enseña.
        country=(equipo.league_name if equipo and equipo.league_name else ""),
        message=mensaje,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        hidden=False,
    )
    session.add(fila)
    await session.commit()
    await session.refresh(fila)
    return _firma(fila)


@router.delete(
    "/guestbook/{entry_id}",
    status_code=204,
    summary="Esconder una firma (moderación)",
)
async def esconder(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    _: m.User = Depends(require_admin),
) -> None:
    """Esconde, no borra. Ver el modelo: sin la fila no hay forma de saber qué
    decía cuando alguien pregunte por qué desapareció."""
    fila = await session.get(m.GuestbookEntry, entry_id)
    if fila is None:
        raise HTTPException(404, "esa firma no existe")
    fila.hidden = True
    await session.commit()
