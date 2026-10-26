"""El turno de un jugador: recorrer la escalera y dejar el fondo como quede.

Esto es la coreografía; las reglas viven en el motor. Lo que aporta este
módulo son las tres economías que el usuario pidió:

1. **Si no hay nada que hacer, no se llama a nadie.** Un jugador con sus seis
   comparables vivos no gasta ni una petición en su turno.
2. **Se para en cuanto el fondo queda completo**, al final de un escalón y
   nunca a mitad: si el sexto y el séptimo se parecen igual, dejar fuera al
   séptimo por orden de llegada sería arbitrario. Por eso se traen todos los
   que haya en el escalón que cierra la cuenta.
3. **Sin puja no se anota nada.** Un precio pedido es lo que una persona
   decidió pedir, no lo que el mercado pagó, y hasta que alguien puje no dice
   nada. Hubo una temporada en que se anotaban como último recurso, para
   preguntarles el precio días después; se quitó el 2026-10-07 cuando se
   midió lo que eran de verdad: de 25 anuncios parecidos a un jugador, 19 no
   tenían ni una puja, y los que entraban por esa puerta lo hacían con precio
   cero.

EL FONDO ES DEL EQUIPO, no del jugador. Cada venta guarda su propio perfil, así
que se vuelve a medir contra quien pregunte: lo encontrado buscando para un
delantero sirve para otro parecido sin gastar una llamada. De paso, cuando tu
jugador sube una habilidad o cumple años no hay nada que borrar, porque sus
comparables se recalculan solos y los que dejan de parecerse se caen.

LO QUE SE LLEVA EL QUE LLAMA. Además del número, la lista de a quién hay que
preguntarle el precio real cuando cierre su subasta. Mientras tanto vale su
puja, que se queda corta: el 2026-10-05 Valerio Cataldi tenía 65.000.000 de
puja y cerró en 77.720.000.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.engines.mercado_comparable import (
    Candidato,
    Estimacion,
    Guardado,
    Objetivo,
    Ventana,
    comparables_de,
    cosecha,
    estimar,
    hay_que_buscar,
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

    #: Las ventas nuevas, para añadir al fondo del equipo.
    nuevas: tuple[Guardado, ...]
    estimacion: Estimacion
    por_resolver: tuple[PorResolver, ...]
    #: Peticiones gastadas. Cero significa que no se pudo buscar: sin las
    #: siete habilidades no hay regla de Hattrick que preguntar.
    busquedas: int
    #: Si se buscó y el fondo siguió sin llegar a `OBJETIVO`.
    agotada: bool
    #: FILAS que devolvió el mercado, no comparables. Es lo que mira el
    #: centinela de la cuota, y la diferencia importa: un jugador que llega y
    #: luego se descarta por no parecerse demuestra que el servidor contestó
    #: igual de bien que uno que se queda.
    filas_vistas: int = 0


async def correr_el_turno(
    objetivo: Objetivo,
    buscar: Buscador,
    *,
    fondo: Sequence[Guardado] = (),
    mi_equipo: int,
    ahora: datetime,
    tambien_para: Sequence[Objetivo] = (),
) -> Resultado:
    """Lo que se hace cuando a un jugador le toca turno.

    Si una búsqueda falla, la excepción sube. Media escalera recorrida daría
    un fondo peor que el que tocaba, y dar un número peor sin avisar es justo
    lo que no debe pasar; quien llame decide si reintenta o si lo deja para la
    semana que viene.

    `tambien_para` es el resto de la plantilla: se guarda lo que le sirva a
    cualquiera de ellos, no sólo a quien disparó la búsqueda. No cambia
    cuándo se para --eso lo sigue decidiendo el que pregunta, que es quien
    tiene turno-- sólo qué se recoge por el camino.

    YA NO HAY NADA QUE RECORRER (2026-10-26). El plan es una sola ventana --la
    de los criterios de Hattrick-- así que esto es un bucle de uno. Se queda
    como bucle a propósito: `plan_de_busqueda` devuelve una tupla y el día que
    vuelva a tener dos ventanas esto no tiene que cambiar.

    Y SE FUE LA PUERTA DE `hay_que_buscar`, que saltaba la búsqueda cuando el
    jugador ya tenía sus ocho comparables vivos. Tenía sentido cuando buscar
    costaba hasta cinco peticiones y el turno era cada cinco semanas: ahorraba
    mucho y se perdía poco. Con el barrido diario el fondo lleno ya no es razón
    para no mirar, porque mirar todos los días ES la medida que se quiere; lo
    que entra hoy es más fresco que lo que había, y una petición por jugador es
    lo que el usuario decidió gastar.
    """
    acumulado = list(fondo)
    busquedas = 0
    nuevas: list[Guardado] = []
    # El plazo no cabe en `Guardado` porque deja de importar en cuanto la venta
    # se resuelve, así que los candidatos viajan en paralelo hasta el final.
    nuevos: list[Candidato] = []

    vistas = 0
    for ventana in plan_de_busqueda(objetivo):
        filas = await buscar(ventana)
        busquedas += 1
        vistas += len(filas)
        con_puja, _sin_puja = cosecha(
            objetivo,
            filas,
            mi_equipo=mi_equipo,
            ya_vistos=[v.ht_player_id for v in acumulado],
            tambien_para=tambien_para,
        )
        for candidato, _peso in con_puja:
            venta = _provisional(candidato, ahora)
            acumulado.append(venta)
            nuevas.append(venta)
            nuevos.append(candidato)

    medidos = comparables_de(acumulado, objetivo, ahora)
    # Se calcula al final y no sobre la marcha: con una sola ventana, «agotada»
    # es simplemente que se buscó y aun así no se llegó a `OBJETIVO`.
    agotada = busquedas > 0 and hay_que_buscar(medidos)
    return Resultado(
        nuevas=tuple(nuevas),
        estimacion=estimar(medidos),
        por_resolver=tuple(
            PorResolver(ht_player_id=c.ht_player_id, plazo=c.plazo, visto_el=ahora) for c in nuevos
        ),
        busquedas=busquedas,
        agotada=agotada,
        filas_vistas=vistas,
    )


def _provisional(candidato: Candidato, ahora: datetime) -> Guardado:
    """El comparable tal como entra, con la puja de precio hasta que se
    resuelva. `firme` queda en falso para que la pantalla pueda avisar."""
    return Guardado(
        ht_player_id=candidato.ht_player_id,
        nombre=candidato.nombre,
        precio=candidato.puja,
        firme=False,
        puja=candidato.puja,
        visto_el=ahora,
        edad=candidato.edad,
        dias=candidato.dias,
        primaria=candidato.primaria,
        secundaria=candidato.secundaria,
        terciaria=candidato.terciaria,
        habilidades=dict(candidato.habilidades),
        especialidad=candidato.especialidad,
        tsi=candidato.tsi,
        pais=candidato.pais,
    )
