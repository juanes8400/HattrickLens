from typing import Any, Protocol


class CHPPGateway(Protocol):
    """Port hacia la CHPP API. La implementación firma OAuth1 y parsea XML."""

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        """Descarga y parsea un file CHPP a dict normalizado.

        Debe respetar: descargas secuenciales por usuario, User-Agent obligatorio,
        retries con backoff, y levantar CHPPAuthError si el token fue revocado.
        """
        ...
