"""El turno de un jugador: recorrer la escalera y dejar el fondo como quede.

Esto es la coreografía; las reglas viven en el motor. Lo que aporta este
módulo son las tres economías que el usuario pidió:

1. **Si no hay nada que hacer, no se llama a nadie.** Un jugador con sus seis
   comparables vivos no gasta ni una petición en su turno.
2. **Se para en cuanto el fondo queda completo**, al final de un escalón y
   nunca a mitad: si el sexto y el séptimo se parecen igual, dejar fuera al
   séptimo por orden de llegada sería arbitrario. Por eso se traen todos los
   que haya en el escalón que cierra la cuenta.
3. **Los anuncios sin puja son el último recurso.** Con puja la venta está
   garantizada; sin ella hay que gastar una resolución para averiguar si
   llegó a venderse, así que sólo se anotan cuando aportan lo bastante como
   para que merezca la pena.

LO QUE SE LLEVA EL QUE LLAMA. Además del fondo nuevo, la lista de a quién hay
que preguntarle el precio real dentro de tres días. Mientras tanto vale su
puja, que se queda corta: el 2026-10-05 Valerio Cataldi tenía 65.000.000 de
puja y cerró en 77.720.000.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.engines.mercado_comparable import (
    MINIMO_PARA_BAJAR_A_SIN_PUJA,
    Candidato,
    Estimacion,
    Guardado,
    Objetivo,
    Ventana,
    admitir,
    cosecha,
    estimar,
    hay_que_buscar,
    perfil_de,
    plan_de_busqueda,
)

#: Lo que tiene que saber hacer quien llame al mercado: recibir una ventana y
#: devolver filas con la forma del parser. Las páginas, los reintentos y el
#: límite de llamadas son suyos.
Buscador = Callable[[Ventana], Awaitable[Sequence[Mapping[str, Any]]]]


@dataclass(frozen=True, slots=True)
class PorResolver:
    """Un anuncio al que hay que preguntarle el precio real cuando cierre."""

    ht_player_id: int
    plazo: str
    visto_el: datetime


@dataclass(frozen=True, slots=True)
class Resultado:
    """Cómo quedó el turno."""

    fondo: tuple[Guardado, ...]
    estimacion: Estimacion
    por_resolver: tuple[PorResolver, ...]
    #: Peticiones gastadas. Cero significa que no hacía falta buscar.
    busquedas: int
    #: Si se recorrió la escalera entera sin llegar a completar el fondo.
    agotada: bool


async def correr_el_turno(
    objetivo: Objetivo,
    buscar: Buscador,
    *,
    guardados: Sequence[Guardado] = (),
    perfil_guardado: tuple[Any, ...] | None = None,
    mi_equipo: int,
    ahora: datetime,
) -> Resultado:
    """Lo que se hace cuando a un jugador le toca turno.

    `perfil_guardado` es la huella que tenía el jugador la última vez. Si no
    coincide con la de ahora, lo acumulado describe a otro jugador (subió una
    habilidad, o cumplió años) y se tira entero: así lo decidió el usuario.

    Si una búsqueda falla, la excepción sube. Media escalera recorrida daría
    un fondo peor que el que tocaba, y dar un número peor sin avisar es justo
    lo que no debe pasar; quien llame decide si reintenta o si lo deja para la
    semana que viene.
    """
    fondo: tuple[Guardado, ...] = tuple(guardados)
    if perfil_guardado is not None and perfil_guardado != perfil_de(objetivo):
        fondo = ()

    if not hay_que_buscar(fondo, ahora):
        return Resultado(
            fondo=fondo,
            estimacion=estimar(fondo),
            por_resolver=(),
            busquedas=0,
            agotada=False,
        )

    busquedas = 0
    agotada = True
    nuevos: list[Candidato] = []
    descartados_sin_puja: list[tuple[Candidato, int]] = []

    for ventana in plan_de_busqueda(objetivo):
        filas = await buscar(ventana)
        busquedas += 1
        con_puja, sin_puja = cosecha(
            objetivo,
            filas,
            mi_equipo=mi_equipo,
            ya_vistos=[g.ht_player_id for g in fondo] + [c.ht_player_id for c in nuevos],
        )
        descartados_sin_puja.extend(sin_puja)
        for candidato, peso in con_puja:
            fondo = admitir(fondo, _provisional(candidato, peso, ahora), objetivo, ahora)
            nuevos.append(candidato)
        if not hay_que_buscar(fondo, ahora):
            agotada = False
            break

    # Último recurso: los que nadie ha pujado todavía. Sólo si son bastantes
    # como para que las resoluciones que cuestan valgan la pena.
    if hay_que_buscar(fondo, ahora) and len(descartados_sin_puja) >= MINIMO_PARA_BAJAR_A_SIN_PUJA:
        for candidato, peso in descartados_sin_puja:
            fondo = admitir(fondo, _provisional(candidato, peso, ahora), objetivo, ahora)
            nuevos.append(candidato)

    dentro = {g.ht_player_id for g in fondo}
    return Resultado(
        fondo=fondo,
        estimacion=estimar(fondo),
        por_resolver=tuple(
            PorResolver(ht_player_id=c.ht_player_id, plazo=c.plazo, visto_el=ahora)
            for c in nuevos
            if c.ht_player_id in dentro
        ),
        busquedas=busquedas,
        agotada=agotada,
    )


def _provisional(candidato: Candidato, peso: int, ahora: datetime) -> Guardado:
    """El comparable tal como entra, con la puja de precio hasta que se
    resuelva. `firme` queda en falso para que la pantalla pueda avisar."""
    return Guardado(
        ht_player_id=candidato.ht_player_id,
        nombre=candidato.nombre,
        precio=candidato.puja,
        peso=peso,
        firme=False,
        visto_el=ahora,
        especialidad=candidato.especialidad,
    )
