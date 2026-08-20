"""Cuánto puede pedir cada usuario, para que uno no se coma la cuota de todos.

La cuota de CHPP es de la APLICACIÓN, no de cada manager: si uno sincroniza en
bucle, Hattrick corta el acceso a todos los usuarios de HT Lens a la vez. Con
un solo usuario eso no importaba; publicada la app es lo primero que puede
tumbarla, y no por mala fe, basta con una pestaña que recargue sola.

Se limita lo que gasta llamadas a Hattrick, no lo que solo lee la base:
sincronizar y abrir la ficha de un rival cuestan ~30 y ~20 peticiones, mientras
que mirar tu economía no cuesta ninguna.

El contador vive en memoria del proceso. Es suficiente para un despliegue de un
solo contenedor, que es el que cabe en un plan gratuito; con varios procesos
cada uno llevaría su cuenta y el límite real sería su suma. Cuando eso importe,
el sitio para arreglarlo es este módulo, no las rutas.
"""
import time
from collections import defaultdict

from fastapi import Depends, HTTPException

from app.api.deps import get_current_user
from app.infrastructure.db import models as m

# Ventana y tope de las operaciones caras. Una sincronización normal tarda
# minutos en aportar algo nuevo (Hattrick actualiza por días), así que seis por
# hora es holgado para cualquier uso humano y ataja el bucle.
VENTANA_SEGUNDOS = 3600
MAXIMO_POR_VENTANA = 6

_marcas: dict[tuple[int, str], list[float]] = defaultdict(list)


def _consumir(user_id: int, cubo: str, maximo: int) -> int | None:
    """Anota una petición y devuelve los segundos que faltan si se pasó."""
    ahora = time.monotonic()
    recientes = [t for t in _marcas[(user_id, cubo)] if ahora - t < VENTANA_SEGUNDOS]
    if len(recientes) >= maximo:
        _marcas[(user_id, cubo)] = recientes
        return int(VENTANA_SEGUNDOS - (ahora - recientes[0])) + 1
    recientes.append(ahora)
    _marcas[(user_id, cubo)] = recientes
    return None


def limite(cubo: str, maximo: int = MAXIMO_POR_VENTANA):
    """Dependencia que limita un tipo de operación cara por usuario.

    Cubos separados a propósito: agotar las sincronizaciones no debe dejarte
    sin poder mirar una ficha de rival, que es otra cosa y otra frecuencia.
    """

    async def guardia(user: m.User = Depends(get_current_user)) -> None:
        espera = _consumir(user.id, cubo, maximo)
        if espera is not None:
            raise HTTPException(
                429,
                f"has alcanzado el límite de {maximo} por hora en esta operación. "
                f"Vuelve a intentarlo en {espera // 60 + 1} minuto(s). "
                "El límite existe porque la cuota de Hattrick es de la aplicación "
                "entera, no de cada usuario.",
                headers={"Retry-After": str(espera)},
            )

    return guardia


def reiniciar() -> None:
    """Vacía los contadores. Solo para los tests."""
    _marcas.clear()
