"""El paso del mercado, de principio a fin.

Esto es lo que se llama desde una sincronización. Hace dos cosas:

1. **Resolver.** A las ventas que entraron con una puja y cuya subasta ya cerró
   se les pregunta cuánto se pagó de verdad. Corre SIEMPRE, en todas las
   sincronizaciones, porque una subasta anotada hoy cierra en días y el margen
   para preguntar son tres (2026-10-26, «lo que fue, fue»).

2. **Barrer.** A cada jugador al que todavía no se le haya mirado hoy se le
   hace UNA búsqueda: la de los criterios de Hattrick. Una vez por día natural
   y por jugador, independiente de cuántas veces se sincronice.

EL BARRIDO DIARIO (2026-10-26, decisión del usuario). Antes esto era semanal:
un disparador --la actualización económica de la liga menos 24 horas-- y un
reparto por turnos que daba a cada jugador la escalera entera cada cinco
semanas y su escalón exacto cada seis días. Ahora le toca a todos todos los
días, con una sola ventana.

EL GASTO, que es lo que decide si esto se puede hacer. Buscar cuesta una
petición por jugador, así que una plantilla de veinticinco son unas veinticinco
al día. Con la escalera entera habrían sido más de cien diarias, y la cuota de
CHPP es de la APLICACIÓN, no de cada manager: lo que uno gasta se lo quita al
resto. El usuario eligió ver el mercado todos los días con menos anchura.

Y EL CENTINELA, sin el cual nada de esto se sostiene. Una cuota agotada no da
error: devuelve cero resultados, exactamente igual que un jugador al que nadie
se parece. Si se diera el día por hecho con la cuota muerta, ese día del
mercado no volvería --el barrido es uno por día-- y además se seguiría
golpeando un servidor que no contesta. Por eso el sello de cada jugador se
estampa sólo cuando de verdad se le buscó, y el barrido se corta entero en
cuanto el canario se queda mudo. Ver `centinela_de_la_cuota`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.mercado_comparable import (
    Resolucion,
    a_quien_le_toca_hoy,
    anotar_si_cambio,
    aplicar_resolucion,
    fondo_del_equipo,
    guardar,
    pendientes_de_resolver,
)
from app.application.queries.mercado_comparable import correr_el_turno
from app.domain.engines.centinela_de_la_cuota import Centinela, canario
from app.domain.engines.mercado_comparable import (
    Objetivo,
    clave_de_criterios,
    comparables_de,
    estimar,
    objetivo_de,
)
from app.infrastructure.db import models as m

_log = logging.getLogger(__name__)

#: Las habilidades que hay que leer del jugador propio. Las ocho, aunque sólo
#: seis cuenten: `terna` se encarga de descartar resistencia y balón parado, y
#: pedirlas todas evita que este módulo tenga que saber cuáles son.
HABILIDADES = (
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
    "stamina",
)


class Historiales(Protocol):
    """Quien sabe traer el historial de traspasos de un jugador.

    Entra como puerto y no como cliente concreto: la capa de aplicacion no
    tiene por que saber que al otro lado hay CHPP, y asi el paso se puede
    probar sin red.
    """

    def __call__(self, ht_player_id: int) -> Awaitable[Mapping[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class PasoDelMercado:
    """Lo que hizo el paso, para poder contarlo en el registro."""

    resueltas: tuple[Resolucion, ...]
    #: A quiénes se les barrió el mercado de verdad. No es «a quiénes les
    #: tocaba»: si el centinela corta a la mitad, aquí están sólo los de antes
    #: del corte, que son los que llevan sello y no repetirán hoy.
    jugadores_barridos: tuple[int, ...]
    ventas_nuevas: int
    busquedas: int
    #: Falso cuando no tocaba nadie y sólo se resolvió lo pendiente.
    se_busco: bool
    #: Cuantos jugadores cambiaron de numero y quedaron anotados en la serie.
    puntos_anotados: int = 0
    #: Verdadero cuando el barrido se cortó porque Hattrick dejó de contestar.
    #: Lo que no se barrió NO lleva sello, así que se reintenta en la
    #: siguiente sincronización en vez de perder el día.
    cuota_agotada: bool = False
    #: Canarios gastados. Es lo que cuesta poder fiarse de los vacíos.
    canarios: int = 0


async def correr_el_paso_del_mercado(
    session: AsyncSession,
    equipo: m.Team,
    *,
    buscar: Any,
    historial_de: Historiales,
    ahora: datetime,
) -> PasoDelMercado:
    """Resuelve lo pendiente y barre el mercado de quien no se haya mirado hoy."""
    resueltas = await _resolver(session, equipo, historial_de, ahora)

    plantilla = await _plantilla(session, equipo.id)
    toca = set(a_quien_le_toca_hoy(plantilla, ahora))
    if not toca:
        # Ya se barrió hoy entero. Aun así una resolución pudo cambiar el
        # número de varios jugadores a la vez: la venta que pasó de puja a
        # precio real es comparable de todo el que se le parezca.
        puntos = await _anotar_la_serie(session, equipo, ahora) if resueltas else 0
        return PasoDelMercado(
            resueltas=resueltas,
            jugadores_barridos=(),
            ventas_nuevas=0,
            busquedas=0,
            se_busco=False,
            puntos_anotados=puntos,
        )

    centinela = Centinela()
    barridos: list[int] = []
    nuevas = 0
    busquedas = 0
    for jugador in plantilla:
        if jugador.ht_player_id not in toca:
            continue
        # EL CANARIO VA ANTES DE GASTAR NADA, y vuelve cuando la racha de
        # vacíos lo pide. Si se queda mudo no es que no haya comparables: es
        # que Hattrick no nos está contestando, y entonces se para aquí sin
        # estampar el sello de nadie más.
        if centinela.hay_que_preguntar:
            filas = await buscar(canario())
            busquedas += 1
            centinela.canto_el_canario(len(filas))
            if not centinela.sigue:
                break
        objetivo = objetivo_de(
            jugador.ht_player_id,
            jugador.edad,
            jugador.habilidades,
            especialidad=jugador.especialidad,
        )
        if objetivo is None:
            # Sin las siete habilidades no hay regla que preguntar. No se
            # estampa el sello: no se ha mirado, así que si mañana llegan sus
            # habilidades le vuelve a tocar.
            continue
        fondo = await fondo_del_equipo(session, equipo.id)
        resultado = await correr_el_turno(
            objetivo,
            buscar,
            fondo=fondo,
            mi_equipo=equipo.ht_team_id,
            ahora=ahora,
            # El resto de la plantilla viaja para quedarse con lo que les
            # sirva a ellos: la búsqueda ya está pagada y por delante pasa
            # el mercado entero, no sólo el de quien tiene turno.
            tambien_para=_otros_objetivos(plantilla, jugador.ht_player_id),
        )
        busquedas += resultado.busquedas
        centinela.vio(resultado.filas_vistas)
        plazos = {p.ht_player_id: p.plazo for p in resultado.por_resolver}
        nuevas += await guardar(session, equipo.id, resultado.nuevas, plazos)
        await _estampar(session, jugador.id, ahora)
        barridos.append(jugador.ht_player_id)
        await session.flush()

    puntos = await _anotar_la_serie(session, equipo, ahora)
    equipo.market_run_at = ahora
    return PasoDelMercado(
        resueltas=resueltas,
        jugadores_barridos=tuple(barridos),
        ventas_nuevas=nuevas,
        puntos_anotados=puntos,
        busquedas=busquedas,
        se_busco=bool(barridos),
        cuota_agotada=centinela.agotada,
        canarios=centinela.canarios,
    )


async def _estampar(session: AsyncSession, player_id: int, ahora: datetime) -> None:
    """Deja dicho que a este jugador ya se le buscó hoy.

    SÓLO DESPUÉS DE HABER BUSCADO DE VERDAD. Es la mitad del centinela que
    vive aquí: un barrido que no llegó a hacerse no deja sello, así que la
    siguiente sincronización lo reintenta en vez de dar el día por medido.
    """
    fila = await session.get(m.Player, player_id)
    if fila is not None:
        fila.market_swept_at = ahora


async def _resolver(
    session: AsyncSession, equipo: m.Team, historial_de: Historiales, ahora: datetime
) -> tuple[Resolucion, ...]:
    """Le pregunta al historial de cada pendiente cuánto se pagó.

    Un fallo al resolver NO tumba el paso: la venta se queda con su puja y se
    reintenta a la siguiente. Perder un precio real es una lástima; perder la
    búsqueda entera por ello sería peor.

    Y NO SE GASTA INTENTO CUANDO NO SE PUDO PREGUNTAR (2026-10-07). Hasta ese
    día un fallo de red o de cuota contaba igual que un «pregunté y no
    estaba», y con dos intentos de presupuesto bastaba con que CHPP fallara
    dos veces seguidas para abandonar una venta que sí existía y cuyo precio
    sí estaba publicado. Los intentos miden lo que sabemos de la venta; una
    llamada que no llegó no sabe nada de ella.
    """
    hechas: list[Resolucion] = []
    for fila in await pendientes_de_resolver(session, equipo.id, ahora):
        try:
            historial = await historial_de(fila.ht_player_id)
        except Exception:  # noqa: BLE001
            # Se registra porque ya no deja ninguna otra huella: desde que
            # no gasta intento, un CHPP caído sería invisible.
            _log.warning(
                "no se pudo preguntar el precio de %s; se reintenta",
                fila.ht_player_id,
                exc_info=True,
            )
            continue
        hechas.append(aplicar_resolucion(fila, historial, ahora))
    if hechas:
        await session.flush()
    return tuple(hechas)


async def _anotar_la_serie(session: AsyncSession, equipo: m.Team, ahora: datetime) -> int:
    """Recorre la plantilla y anota un punto por cada estimacion que cambio.

    Se hace para TODOS, no solo para los del turno: el fondo es del equipo,
    asi que una venta nueva o una resolucion puede mover el numero de
    cualquiera que se le parezca. Es aritmetica sobre lo ya guardado y no
    gasta ni una peticion a Hattrick.
    """
    plantilla = await _plantilla(session, equipo.id)
    fondo = await fondo_del_equipo(session, equipo.id)
    puntos = 0
    for jugador in plantilla:
        objetivo = objetivo_de(
            jugador.ht_player_id,
            jugador.edad,
            jugador.habilidades,
            especialidad=jugador.especialidad,
        )
        if objetivo is None:
            continue
        estimacion = estimar(comparables_de(fondo, objetivo, ahora))
        if await anotar_si_cambio(
            session,
            equipo.id,
            jugador.ht_player_id,
            estimacion,
            ahora,
            clave_de_criterios(objetivo),
        ):
            puntos += 1
    if puntos:
        await session.flush()
    return puntos


def _otros_objetivos(plantilla: Sequence[_Jugador], menos_este: int) -> tuple[Objetivo, ...]:
    """Los demás de la plantilla, como objetivos medibles."""
    salida = []
    for j in plantilla:
        if j.ht_player_id == menos_este:
            continue
        otro = objetivo_de(j.ht_player_id, j.edad, j.habilidades, especialidad=j.especialidad)
        if otro is not None:
            salida.append(otro)
    return tuple(salida)


@dataclass(frozen=True, slots=True)
class _Jugador:
    #: La fila de `players`, para poder estampar el sello del barrido.
    id: int
    ht_player_id: int
    edad: int
    especialidad: int
    habilidades: dict[str, int]
    #: Cuándo se le barrió el mercado por última vez. Cumple `_ConSello`.
    market_swept_at: datetime | None


async def _plantilla(session: AsyncSession, team_id: int) -> list[_Jugador]:
    """La plantilla de hoy, con la foto más reciente de cada jugador.

    LOS QUE SE FUERON NO CUENTAN, y hasta el 2026-10-07 sí contaban. La
    tabla guarda a todo el que pasó alguna vez por el club --555 filas con
    este equipo, 530 de ellas de gente que ya salió-- y sin filtrar por
    `left_team_at` el paso repartía turnos entre ex jugadores y gastaba
    peticiones de CHPP buscándole comparables a quien ya no es tuyo.

    Se vio al contar los puntos de la serie: salieron 48 jugadores donde la
    plantilla tiene 25.
    """
    jugadores = (
        await session.execute(
            select(m.Player).where(
                m.Player.team_id == team_id,
                m.Player.left_team_at.is_(None),
            )
        )
    ).scalars()
    salida: list[_Jugador] = []
    for jugador in jugadores:
        foto = (
            await session.execute(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == jugador.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if foto is None:
            continue
        salida.append(
            _Jugador(
                id=jugador.id,
                ht_player_id=jugador.ht_player_id,
                market_swept_at=jugador.market_swept_at,
                edad=foto.age_years or 0,
                especialidad=foto.specialty or 0,
                habilidades={h: getattr(foto, h, 0) or 0 for h in HABILIDADES},
            )
        )
    return salida
