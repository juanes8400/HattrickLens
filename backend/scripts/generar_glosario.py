"""Genera el glosario oficial de Hattrick para cada idioma de la app.

2026-09-15, traducción de HT Lens. Descarga `translations.xml` 1.2 de cada
idioma con el token de la base local, lo lee con `leer_translations` y lo deja
como JSON en dos sitios, para que frontend y backend digan lo mismo:

    frontend/src/i18n/glosario/<idioma>.json
    backend/app/config/glosario/<idioma>.json

Se guarda en el repositorio y no se pide en cada arranque: el vocabulario de
Hattrick casi no cambia, y así la app no depende de Hattrick para mostrar una
palabra. Se vuelve a correr cuando se añade un idioma o cambia el juego.

Uso:
    python scripts/generar_glosario.py
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.core.config import settings  # noqa: E402
from app.infrastructure.chpp.client import CHPPClient  # noqa: E402
from app.infrastructure.chpp.glosario import leer_translations  # noqa: E402
from app.infrastructure.security.tokens import decrypt_token  # noqa: E402

#: Código de la app → `LanguageID` de Hattrick (ver `worldlanguages.xml`).
#: El español es el de España (6): es el que se copió a mano en su día y el que
#: la app ya enseña, así que no cambia ni una palabra. El inglés es el británico
#: (2) y no el de EE. UU. (151).
#:
#: Los números NO se inventan: salen de `worldlanguages.xml`, que es la lista
#: que publica el propio juego. Para añadir un idioma, pídela y busca el suyo.
#: Así entró el alemán (3) el 2026-09-29: se descargó la lista y se leyó, en vez
#: de suponer que el 3 le tocaba por orden alfabético o por tamaño del país. El
#: polaco (13) entró igual el mismo día, y su número no lo habría acertado nadie
#: de memoria.
IDIOMAS: dict[str, int] = {"es": 6, "en": 2, "it": 4, "de": 3, "pl": 13}

DESTINOS = [
    RAIZ.parent / "frontend" / "src" / "i18n" / "glosario",
    RAIZ / "app" / "config" / "glosario",
]


async def main() -> None:
    con = sqlite3.connect(f"file:{RAIZ / 'dev.db'}?mode=ro", uri=True)
    fila = con.execute(
        "select oauth_token_enc, oauth_secret_enc from chpp_tokens "
        "where status = 'active' order by id limit 1"
    ).fetchone()
    con.close()
    if fila is None:
        raise SystemExit("no hay un token activo en dev.db: conecta la app en local primero")

    client = CHPPClient(decrypt_token(fila[0]), decrypt_token(fila[1]))
    url = f"{settings.chpp_base_url}/chppxml.ashx"
    try:
        for codigo, language_id in IDIOMAS.items():
            respuesta = await client._get_con_reintentos(
                url, {"file": "translations", "version": "1.2", "languageId": language_id}
            )
            respuesta.raise_for_status()
            glosario = leer_translations(respuesta.content)
            texto = json.dumps(glosario, ensure_ascii=False, indent=2) + "\n"
            for destino in DESTINOS:
                destino.mkdir(parents=True, exist_ok=True)
                # En bytes y no `write_text`: en Windows ese volteaba los
                # saltos de linea a CRLF y el diff salia con los tres
                # ficheros cambiados enteros sin cambiar una palabra.
                (destino / f"{codigo}.json").write_bytes(texto.encode("utf-8"))
            print(f"{codigo}: {glosario['idioma']['nombre']} ({len(texto)} caracteres)")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
