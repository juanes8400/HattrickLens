"""Traducción de las respuestas del servidor (2026-09-15).

El servidor calcula y escribe en español, y así se queda por dentro: las
comparaciones, las claves y los tests no cambian. La traducción ocurre al
SALIR, en la respuesta, cuando el navegador pide otro idioma con la cabecera
``Accept-Language``.

Cómo se traduce un texto:

1. Tal cual, si está en el diccionario (``en.json``): «Encantados» →
   «satisfied».
2. Por plantilla, si salió de un f-string: el diccionario guarda
   ``"{} está lesionado": "{} is injured"`` y aquí se convierte en una
   expresión que reconoce «Luis Bango está lesionado». Los huecos se
   traducen a su vez, por si llevan otro texto del diccionario dentro.
3. Si no encaja nada, se deja en español. Nunca un hueco.

Hay campos que NO se traducen aunque tengan español: son claves con las que
el frontend decide cosas (``category``, ``key``, ``module``…). Traducirlos
rompería esas decisiones; el frontend ya los traduce por su cuenta.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

_CARPETA = Path(__file__).resolve().parent

#: Campos cuyo valor es una clave de lógica, no un texto para leer.
CAMPOS_INTOCABLES = frozenset(
    {
        "category",
        "key",
        "module",
        "severity",
        "kind",
        "direction",
        "salarySource",
        "source",
        "tone",
        "specialty",
        "impact",
        "status",
        "type",
        "chart",
        "display",
        "region",
        "code",
        "id",
        "live",
        "href",
        "ruta",
        "url",
        "position",
        "basePosition",
        "behaviour",
        "puesto",
        "skill",
        "result",
        "seasonAtSale",
        "derivedTrainingSkill",
        "topSkillAtSale",
        "name",
        "teamName",
        "player",
        "opponent",
        "rival",
        "home",
        "away",
        "email",
    }
)

IDIOMAS = ("es", "en")


def idioma_de(cabecera: str | None) -> str:
    """El primer idioma soportado de ``Accept-Language``; español si no hay."""
    for parte in (cabecera or "").split(","):
        codigo = parte.split(";")[0].strip().lower()[:2]
        if codigo in IDIOMAS:
            return codigo
    return "es"


class Traductor:
    def __init__(self, diccionario: dict[str, str]) -> None:
        self._exactos: dict[str, str] = {}
        plantillas: list[tuple[re.Pattern[str], str, str]] = []
        for origen, destino in diccionario.items():
            if not destino:
                continue
            if "{}" in origen:
                plantillas.append(self._compilar(origen, destino))
            else:
                self._exactos[origen] = destino
        # Las más largas primero: «{} de {} en total» antes que «{} de {}».
        plantillas.sort(key=lambda p: len(p[2]), reverse=True)
        self._plantillas = plantillas

    @staticmethod
    def _compilar(origen: str, destino: str) -> tuple[re.Pattern[str], str, str]:
        literal = origen.replace("{{", "\x00").replace("}}", "\x01")
        trozos = literal.split("{}")
        patron = "(.+?)".join(
            re.escape(t.replace("\x00", "{").replace("\x01", "}")) for t in trozos
        )
        return re.compile(f"^{patron}$", re.DOTALL), destino, max(trozos, key=len)

    def texto(self, valor: str) -> str:
        if not valor or not any(c.isalpha() for c in valor):
            return valor
        exacto = self._exactos.get(valor)
        if exacto is not None:
            return exacto
        recortado = valor.strip()
        if recortado != valor:
            exacto = self._exactos.get(recortado)
            if exacto is not None:
                return valor.replace(recortado, exacto)
        for patron, destino, pista in self._plantillas:
            pista_limpia = pista.replace("\x00", "{").replace("\x01", "}")
            if pista_limpia and pista_limpia not in valor:
                continue
            encaje = patron.match(valor)
            if encaje:
                huecos = [self.texto(g) for g in encaje.groups()]
                return self._rellenar(destino, huecos)
        return valor

    @staticmethod
    def _rellenar(destino: str, huecos: Iterable[str]) -> str:
        """Pone cada hueco en su ``{}``, o en ``{0}``, ``{1}`` si cambian de orden."""
        lista = list(huecos)
        if re.search(r"\{\d+\}", destino):
            return re.sub(
                r"\{(\d+)\}",
                lambda m: lista[int(m.group(1))] if int(m.group(1)) < len(lista) else m.group(0),
                destino,
            )
        partes = destino.split("{}")
        salida = partes[0]
        for i, parte in enumerate(partes[1:]):
            salida += (lista[i] if i < len(lista) else "") + parte
        return salida

    def json(self, dato: Any, campo: str | None = None) -> Any:
        if campo in CAMPOS_INTOCABLES:
            return dato
        if isinstance(dato, str):
            return self.texto(dato)
        if isinstance(dato, list):
            return [self.json(x, campo) for x in dato]
        if isinstance(dato, dict):
            return {k: self.json(v, k) for k, v in dato.items()}
        return dato


@lru_cache(maxsize=len(IDIOMAS))
def traductor(idioma: str) -> Traductor | None:
    """El traductor de un idioma, o ``None`` para español (no hay nada que hacer)."""
    if idioma == "es":
        return None
    ruta = _CARPETA / f"{idioma}.json"
    if not ruta.exists():
        return None
    return Traductor(json.loads(ruta.read_text(encoding="utf-8")))
