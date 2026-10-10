"""Lo que ha costado la gente parecida a un jugador tuyo, para la pantalla.

No llama a Hattrick ni una vez: todo sale del fondo que dejó el paso semanal,
así que abrir la ficha de un jugador es gratis y se puede recalcular tantas
veces como haga falta. Por eso tampoco hay nada que invalidar cuando el jugador
sube una habilidad o cumple años: sus comparables se vuelven a medir contra el
jugador de hoy y los que dejan de parecerse se caen solos.

Lo que la pantalla está obligada a decir, y por eso viaja aquí:

· **Cuántos son provisionales.** Una venta entra con la puja de precio hasta
  que su subasta cierra. La puja se queda corta: el 2026-10-05 Valerio Cataldi
  tenía 65.000.000 de puja y cerró en 77.720.000, un 16% más.
· **De cuándo es lo más viejo.** Una venta sigue contando pasadas las siete
  semanas si no apareció nada mejor, y entonces el número habla de un mercado
  que puede haber cambiado.
· **Cuánto se parecen de verdad.** El peso de cada uno, para que se vea si el
  número sale de gemelos o de primos lejanos.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.mercado_comparable import a_guardado
from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    VIDA,
    Guardado,
    Objetivo,
    comparables_de,
    estimar,
    objetivo_de,
)
from app.domain.value_objects.ht_constants import SPECIALTIES
from app.infrastructure.db import models as m

#: Las ocho habilidades del jugador propio. `terna` descarta resistencia y
#: balón parado; pedirlas todas evita que este módulo tenga que saber cuáles.
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


@dataclass(frozen=True, slots=True)
class RasgoVisible:
    """Una habilidad y su nivel, SIN formatear.

    El nombre sale con la clave interna a proposito: quien lo pinte tiene el
    glosario oficial de Hattrick y sabe como se llama «scoring» en el idioma
    de quien mira. Montar aqui la cadena obligaria a traducir en el servidor,
    que no sabe el idioma, y fue justo el fallo que se vio en pantalla el
    2026-10-06: el perfil salia como «scoring 18 - passing 13».
    """

    habilidad: str
    nivel: int


@dataclass(frozen=True, slots=True)
class FilaDeComparable:
    """Una venta, tal como se enseña."""

    ht_player_id: int
    nombre: str
    #: El precio que cuenta: el de cierre si ya se resolvio, la puja si no.
    precio: int
    #: La puja con la que entro, siempre. Junto a `precio` y `firme` deja
    #: ver cuanto se quedo corta.
    puja: int
    peso: int
    firme: bool
    #: Si entra en el numero. Falso solo para un provisional abandonado.
    cuenta: bool
    viejo: bool
    edad: int
    perfil: tuple[RasgoVisible, RasgoVisible, RasgoVisible]
    semanas: int
    #: Cuándo cierra su subasta, mientras siga siendo una puja. Es lo que
    #: dice cuánto le falta al número para ser de fiar, así que la pantalla
    #: lo enseña en vez de dejarlo sólo en la cola de resolución.
    cierra: datetime | None
    #: El NOMBRE, no el número: es lo que el resto de la aplicación manda y
    #: lo que el componente del icono sabe leer (`SPECIALTIES` del dominio).
    especialidad: str
    tsi: int
    #: El código de dos letras, que es lo que pinta la bandera. Vacío cuando
    #: la venta se anotó antes de que se guardara el país.
    pais_codigo: str
    pais_nombre: str
    #: Si esta fila es el jugador que pregunta, y no una venta. Va primera en
    #: la tabla y sombreada, para comparar contra ella sin buscarla
    #: (2026-10-09, pedido del usuario). No tiene precio ni plazo: no está en
    #: venta, está de referencia.
    propio: bool = False


@dataclass(frozen=True, slots=True)
class PuntoDeLaSerie:
    """Una lectura pasada, para dibujar como fue cambiando.

    `precios` es la nube entera de esa lectura, no sólo la media: la
    dispersión es la mitad de lo que hay que juzgar. El 2026-10-07 un
    jugador tenía media 438.701 y sus siete ventas iban de 1.000 a
    1.326.000; decir sólo la media callaba eso.
    """

    cuando: datetime
    media: int | None
    mediana: int | None
    n: int
    #: `[(precio, firme, peso), ...]` ya convertidos a la moneda del equipo.
    #: El peso es el «se parece» de esa venta, de 0 a 100: la grafica pinta
    #: mas pequeño y mas suave lo que se parece menos. Las lecturas anotadas
    #: antes del 2026-10-09 no lo guardaron y salen a 100.
    precios: tuple[tuple[int, bool, int], ...]


@dataclass(frozen=True, slots=True)
class PrecioComparable:
    """El número y todo lo que hace falta para no leerlo mal."""

    #: `None` mientras no haya bastantes ventas.
    media: int | None
    mediana: int | None
    #: Los dos extremos de lo que de verdad se pagó.
    minimo: int | None
    maximo: int | None
    n: int
    faltan: int
    peso_minimo: int
    provisionales: int
    #: Semanas de la venta más vieja de las que cuentan.
    semanas_del_mas_viejo: int
    #: El perfil con el que se buscó, para que se vea contra qué se compara.
    perfil: tuple[RasgoVisible, RasgoVisible, RasgoVisible]
    #: Cómo se llama el dinero que se está enseñando. Todas las cifras de
    #: aquí ya vienen divididas por la tasa del país.
    moneda: str
    comparables: tuple[FilaDeComparable, ...]
    #: De la más vieja a la más nueva. Vacía mientras no haya historia.
    serie: tuple[PuntoDeLaSerie, ...]
    #: El jugador que pregunta, con la misma forma que una venta, para
    #: encabezar la tabla. `None` sólo si falta su foto.
    jugador: FilaDeComparable | None = None


async def precio_de(
    session: AsyncSession,
    team_id: int,
    ht_player_id: int,
    ahora: datetime | None = None,
) -> PrecioComparable | None:
    """El precio de un jugador, o `None` si ese jugador no es de este equipo."""
    momento = ahora or datetime.now(UTC)
    objetivo, ficha, foto = await _objetivo_del_jugador(session, team_id, ht_player_id)
    if objetivo is None or ficha is None or foto is None:
        return None

    # El dinero de CHPP viene en la moneda base del juego. Dividir por la
    # tasa del país es lo que hace el resto de la aplicación, y este panel
    # era el único que no lo hacía.
    equipo = await session.get(m.Team, team_id)
    tasa = (equipo.currency_rate or 1.0) if equipo else 1.0
    moneda = (equipo.currency_name if equipo else "") or ""

    def convertido(v: int) -> int:
        return int(round(v / tasa)) if tasa else int(v)

    paises = await _paises(session)

    filas = list(
        (
            await session.execute(select(m.MarketSale).where(m.MarketSale.team_id == team_id))
        ).scalars()
    )
    # El plazo no viaja dentro de `Guardado` --deja de importar en cuanto la
    # venta se resuelve-- así que se queda aquí al lado, por identificador.
    plazos = {f.ht_player_id: f.deadline for f in filas}
    elegidos = comparables_de([a_guardado(f) for f in filas], objetivo, momento)
    estimacion = estimar(elegidos)
    precios = [c.venta.precio for c in elegidos]

    return PrecioComparable(
        media=convertido(estimacion.media) if estimacion.media is not None else None,
        mediana=convertido(estimacion.mediana) if estimacion.mediana is not None else None,
        minimo=convertido(min(precios)) if estimacion.suficiente else None,
        maximo=convertido(max(precios)) if estimacion.suficiente else None,
        n=estimacion.n,
        faltan=max(0, OBJETIVO - estimacion.n),
        peso_minimo=estimacion.peso_minimo,
        provisionales=estimacion.provisionales,
        semanas_del_mas_viejo=max(
            (_semanas(c.venta.visto_el, momento) for c in elegidos), default=0
        ),
        perfil=_perfil(objetivo),
        moneda=moneda,
        serie=await _serie(session, team_id, ht_player_id, convertido),
        # La fila de referencia: el propio jugador, con la misma forma que una
        # venta para que la tabla no tenga que saber que es distinto. Se parece
        # a si mismo un 100 %, y no tiene precio ni plazo porque no esta en
        # venta.
        jugador=FilaDeComparable(
            ht_player_id=ht_player_id,
            nombre=f"{ficha.first_name} {ficha.last_name}".strip(),
            precio=0,
            puja=0,
            peso=100,
            firme=False,
            cuenta=False,
            viejo=False,
            edad=foto.age_years or 0,
            perfil=_perfil(objetivo),
            semanas=0,
            cierra=None,
            especialidad=SPECIALTIES.get(foto.specialty or 0, ""),
            tsi=foto.tsi or 0,
            pais_codigo=paises.get(foto.country_id or 0, ("", ""))[0],
            pais_nombre=paises.get(foto.country_id or 0, ("", ""))[1],
            propio=True,
        ),
        comparables=tuple(
            FilaDeComparable(
                ht_player_id=c.venta.ht_player_id,
                nombre=c.venta.nombre,
                precio=convertido(c.venta.precio),
                puja=convertido(c.venta.puja),
                cuenta=c.cuenta,
                peso=c.peso,
                firme=c.venta.firme,
                viejo=c.viejo,
                edad=c.venta.edad,
                perfil=_perfil(c.venta),
                semanas=_semanas(c.venta.visto_el, momento),
                cierra=plazos.get(c.venta.ht_player_id),
                especialidad=SPECIALTIES.get(c.venta.especialidad, ""),
                tsi=c.venta.tsi,
                pais_codigo=paises.get(c.venta.pais, ("", ""))[0],
                pais_nombre=paises.get(c.venta.pais, ("", ""))[1],
            )
            for c in elegidos
        ),
    )


async def _objetivo_del_jugador(
    session: AsyncSession, team_id: int, ht_player_id: int
) -> tuple[Objetivo | None, m.Player | None, m.PlayerSnapshot | None]:
    """El perfil con el que se busca, y de paso su ficha y su foto.

    Devuelve las tres cosas porque la pantalla encabeza la tabla con el propio
    jugador (2026-10-09) y necesita su nombre, su edad, su TSI, su país y su
    especialidad. Pedirlas otra vez por separado seria repetir las mismas dos
    consultas.
    """
    jugador = (
        await session.execute(
            select(m.Player).where(
                m.Player.team_id == team_id, m.Player.ht_player_id == ht_player_id
            )
        )
    ).scalar_one_or_none()
    if jugador is None:
        return None, None, None
    foto = (
        await session.execute(
            select(m.PlayerSnapshot)
            .where(m.PlayerSnapshot.player_id == jugador.id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if foto is None:
        return None, jugador, None
    return (
        objetivo_de(
            ht_player_id,
            foto.age_years or 0,
            {h: getattr(foto, h, 0) or 0 for h in HABILIDADES},
            especialidad=foto.specialty or 0,
        ),
        jugador,
        foto,
    )


async def _serie(
    session: AsyncSession,
    team_id: int,
    ht_player_id: int,
    convertido: Callable[[int], int],
) -> tuple[PuntoDeLaSerie, ...]:
    """Las lecturas pasadas de este jugador, de la más vieja a la más nueva.

    Sale de `market_estimates`, que guarda una fila por cada vez que su
    número cambió. No se puede reconstruir del fondo: al resolver una venta,
    su puja se pisa con el precio de cierre y el valor anterior desaparece.
    """
    filas = (
        (
            await session.execute(
                select(m.MarketEstimate)
                .where(
                    m.MarketEstimate.team_id == team_id,
                    m.MarketEstimate.ht_player_id == ht_player_id,
                )
                .order_by(m.MarketEstimate.captured_at)
            )
        )
        .scalars()
        .all()
    )
    puntos = []
    for fila in filas:
        try:
            nube = json.loads(fila.prices_json or "[]")
        except ValueError:
            nube = []
        puntos.append(
            PuntoDeLaSerie(
                cuando=fila.captured_at,
                media=convertido(fila.mean_price) if fila.mean_price is not None else None,
                mediana=convertido(fila.median_price) if fila.median_price is not None else None,
                n=fila.n,
                precios=tuple(
                    (
                        convertido(int(p.get("precio", 0) or 0)),
                        bool(p.get("firme")),
                        int(p.get("peso", 100) or 100),
                    )
                    for p in nube
                    if isinstance(p, dict)
                ),
            )
        )
    return tuple(puntos)


async def _paises(session: AsyncSession) -> dict[int, tuple[str, str]]:
    """El código y el nombre de cada país, por identificador de Hattrick.

    Sale de `WorldContext`, que es de donde lo saca Saldo por jugador para
    pintar la misma bandera; aquí se usa el mismo sitio para que las dos
    tablas no puedan discrepar.
    """
    filas = (
        await session.execute(
            select(
                m.WorldContext.country_id,
                m.WorldContext.country_code,
                m.WorldContext.country_name,
            ).where(m.WorldContext.country_code != "")
        )
    ).all()
    return {int(pais): (str(codigo).upper(), str(nombre or "")) for pais, codigo, nombre in filas}


def _perfil(quien: Objetivo | Guardado) -> tuple[RasgoVisible, RasgoVisible, RasgoVisible]:
    """Las tres habilidades que deciden el parecido, sin formatear."""
    return (
        RasgoVisible(quien.primaria.habilidad, quien.primaria.nivel),
        RasgoVisible(quien.secundaria.habilidad, quien.secundaria.nivel),
        RasgoVisible(quien.terciaria.habilidad, quien.terciaria.nivel),
    )


def _semanas(desde: datetime, ahora: datetime) -> int:
    inicio = desde if desde.tzinfo is not None else desde.replace(tzinfo=UTC)
    fin = ahora if ahora.tzinfo is not None else ahora.replace(tzinfo=UTC)
    return max(0, int((fin - inicio) / VIDA * 7))
