"""Lo que ha costado la gente parecida a un jugador tuyo, para la pantalla.

No llama a Hattrick ni una vez: todo sale del fondo que dejó el paso del mercado,
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
from app.domain.engines.criterios_hattrick import criterios_de, liston_de, rareza
from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    PESO_DEL_CLAVADO,
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
    #: Si el propio Hattrick ensenaria esta venta al comparar a este jugador
    #: (2026-10-10). Va aparte de `peso`, que es nuestro: sirve para poder
    #: decir «esto lo avalaria el juego». Falso en las ventas guardadas antes
    #: de que se empezaran a anotar las siete habilidades.
    avalado_por_hattrick: bool
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
class CriterioVisible:
    """Un filtro de los que usaría el propio Hattrick, SIN formatear.

    Igual que `RasgoVisible`, la habilidad va con su clave interna: quien lo
    pinte tiene el glosario oficial y sabe cómo se llama «set_pieces» en el
    idioma de quien mira.

    `operador` dice cómo leer los dos números: `=` es un nivel clavado y
    `minimo` y `maximo` valen lo mismo; `banda` es un rango de verdad; `<=` es
    un techo y `minimo` es cero. Son los tres que usa el juego.
    """

    habilidad: str
    operador: str
    minimo: int
    maximo: int


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
    #: LOS FILTROS DEL PROPIO HATTRICK, que es lo único que la pantalla no
    #: podía decir y nadie más puede (2026-10-27). Hasta hoy enseñaba las
    #: ventas y el número, pero no POR QUÉ esas ventas y no otras; y el por qué
    #: está medido, no supuesto: 612 comprobaciones y un 98 % fuera de muestra.
    criterios: tuple[CriterioVisible, ...]
    edad_minima: int
    edad_maxima: int
    #: El dial, con los dos números que lo deciden, para que «la búsqueda salió
    #: ancha» no sea una afirmación sin cuentas: `rareza` contra `liston`.
    dial_holgado: bool
    rareza: int
    liston: int
    #: El tope de días que Hattrick añade a los 17 años, o `None`. No sale en
    #: la cadena de criterios del juego pero sí filtra, así que se enseña.
    tope_de_dias: int | None
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
    # SOLO LAS QUE CUENTAN, o sea las ventas CERRADAS. `elegidos` lleva también
    # las subastas vivas para poder enseñarlas, y una puja no es un precio
    # (2026-10-09): se queda corta y siempre por el mismo lado --Valerio
    # Cataldi, 65.000.000 de puja y 77.720.000 de cierre--. Mezclarlas en el
    # rango lo bajaría sin decirlo.
    precios = [c.venta.precio for c in elegidos if c.cuenta]
    # Los filtros del juego para ESTE jugador. Es una función pura del dominio,
    # sin consultas ni cuota: la misma que decide si una venta lleva el sello.
    niveles = dict(objetivo.habilidades)
    criterios = criterios_de(objetivo.edad, niveles)

    return PrecioComparable(
        media=convertido(estimacion.media) if estimacion.media is not None else None,
        mediana=convertido(estimacion.mediana) if estimacion.mediana is not None else None,
        # EL RANGO VA CON EL NUMERO, no con las ocho (2026-10-26). Sale de los
        # mismos precios que la media, así que enseñar la media y esconder el
        # rango sería decir «sé el promedio de estos tres pero no el menor de
        # los tres». `n` y `faltan` son los que dicen cuánto fiarse.
        minimo=convertido(min(precios)) if precios else None,
        maximo=convertido(max(precios)) if precios else None,
        n=estimacion.n,
        faltan=max(0, OBJETIVO - estimacion.n),
        peso_minimo=estimacion.peso_minimo,
        provisionales=estimacion.provisionales,
        semanas_del_mas_viejo=max(
            (_semanas(c.venta.visto_el, momento) for c in elegidos), default=0
        ),
        perfil=_perfil(objetivo),
        criterios=tuple(
            CriterioVisible(
                habilidad=c.habilidad,
                operador=c.operador,
                minimo=c.minimo,
                maximo=c.maximo,
            )
            for c in criterios.habilidades
        ),
        edad_minima=criterios.edad_minima,
        edad_maxima=criterios.edad_maxima,
        dial_holgado=criterios.holgado,
        rareza=rareza(niveles),
        liston=liston_de(niveles),
        tope_de_dias=criterios.tope_de_dias,
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
            avalado_por_hattrick=False,
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
                avalado_por_hattrick=c.avalado_por_hattrick,
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


@dataclass(frozen=True, slots=True)
class PrecioDeUnJugador:
    """El precio comparable de UN jugador, para la tabla de la plantilla.

    Es el resumen de `PrecioComparable`, sin la lista de ventas ni los
    criterios: la tabla enseña una fila por jugador y el detalle está a un clic
    en su ficha. Lo que sí lleva es de qué está hecho el número, porque una
    cifra sin eso al lado invita a creérsela.
    """

    ht_player_id: int
    nombre: str
    edad: int
    tsi: int
    especialidad: str
    perfil: tuple[RasgoVisible, RasgoVisible, RasgoVisible]
    #: `None` cuando no hay ni una venta cerrada parecida. NUNCA cero: cero
    #: sería decir que no vale nada, y lo que pasa es que no se sabe.
    media: int | None
    mediana: int | None
    minimo: int | None
    maximo: int | None
    n: int
    faltan: int
    #: Cuántas de las que cuentan son clavadas, o sea el mismo jugador. El
    #: resto son avaladas: sólo hay dos pesos desde el 2026-10-27.
    clavadas: int
    avaladas: int
    #: Subastas abiertas que se enseñan pero NO promedian.
    provisionales: int
    semanas_del_mas_viejo: int
    #: Las medias de las lecturas pasadas del tramo vigente, de la más vieja a
    #: la más nueva, para dibujar una chispa. Vacía mientras no haya historia.
    serie: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PreciosDeLaPlantilla:
    """Lo que ha costado gente parecida a cada uno de los tuyos."""

    moneda: str
    jugadores: tuple[PrecioDeUnJugador, ...]


async def precios_de_la_plantilla(
    session: AsyncSession,
    team_id: int,
    ahora: datetime | None = None,
) -> PreciosDeLaPlantilla:
    """El precio comparable de TODA la plantilla, de una sentada.

    POR QUÉ EN PLURAL Y NO LLAMANDO VEINTICINCO VECES A `precio_de`
    (2026-10-27, pedido del usuario: «dentro de Transferencias/Mi Plantilla,
    debemos ver una tabla con el Precio y algunos daticos»). El fondo del
    mercado es del EQUIPO, no de cada jugador: se lee una vez y se mide contra
    todos. Pedirlo jugador a jugador leería las mismas ventas veinticinco
    veces, y además dejaría la puerta abierta a que la tabla y la ficha
    enseñaran dos números distintos del mismo jugador.

    No gasta ni una consulta a Hattrick, igual que la ficha: todo sale del
    fondo que dejó el paso del mercado.
    """
    momento = ahora or datetime.now(UTC)
    equipo = await session.get(m.Team, team_id)
    tasa = (equipo.currency_rate or 1.0) if equipo else 1.0
    moneda = (equipo.currency_name if equipo else "") or ""

    def convertido(v: int) -> int:
        return int(round(v / tasa)) if tasa else int(v)

    guardadas = [
        a_guardado(f)
        for f in (
            await session.execute(select(m.MarketSale).where(m.MarketSale.team_id == team_id))
        ).scalars()
    ]
    series = await _series_de_la_plantilla(session, team_id, convertido)

    filas: list[PrecioDeUnJugador] = []
    for jugador, foto in await _plantilla_con_foto(session, team_id):
        objetivo = objetivo_de(
            jugador.ht_player_id,
            foto.age_years or 0,
            {h: getattr(foto, h, 0) or 0 for h in HABILIDADES},
            especialidad=foto.specialty or 0,
        )
        if objetivo is None:
            continue
        elegidos = comparables_de(guardadas, objetivo, momento)
        estimacion = estimar(elegidos)
        precios = [c.venta.precio for c in elegidos if c.cuenta]
        cuentan = [c for c in elegidos if c.cuenta]
        clavadas = sum(1 for c in cuentan if c.peso >= PESO_DEL_CLAVADO)
        filas.append(
            PrecioDeUnJugador(
                ht_player_id=jugador.ht_player_id,
                nombre=f"{jugador.first_name} {jugador.last_name}".strip(),
                edad=foto.age_years or 0,
                tsi=foto.tsi or 0,
                especialidad=SPECIALTIES.get(foto.specialty or 0, ""),
                perfil=_perfil(objetivo),
                media=convertido(estimacion.media) if estimacion.media is not None else None,
                mediana=(
                    convertido(estimacion.mediana) if estimacion.mediana is not None else None
                ),
                minimo=convertido(min(precios)) if precios else None,
                maximo=convertido(max(precios)) if precios else None,
                n=estimacion.n,
                faltan=max(0, OBJETIVO - estimacion.n),
                clavadas=clavadas,
                avaladas=len(cuentan) - clavadas,
                provisionales=estimacion.provisionales,
                semanas_del_mas_viejo=max(
                    (_semanas(c.venta.visto_el, momento) for c in elegidos), default=0
                ),
                serie=series.get(jugador.ht_player_id, ()),
            )
        )
    return PreciosDeLaPlantilla(moneda=moneda, jugadores=tuple(filas))


async def _plantilla_con_foto(
    session: AsyncSession, team_id: int
) -> list[tuple[m.Player, m.PlayerSnapshot]]:
    """La plantilla DE HOY, con la foto más reciente de cada jugador.

    Los que no tienen ni una foto se quedan fuera: sin habilidades no hay
    terna, y sin terna no hay a quién parecerse.

    Y LOS QUE SE FUERON TAMPOCO CUENTAN. La tabla guarda a todo el que pasó
    alguna vez por el club --556 filas con este equipo, 531 de gente que ya
    salió-- así que sin `left_team_at` esta consulta medía el fondo contra
    cincuenta jugadores donde la plantilla tiene veinticinco: la mitad del
    trabajo era buscarle comparables a un ex.

    ES EL MISMO FALLO QUE YA SE ARREGLÓ EL 2026-10-07 en `_plantilla` del paso
    del mercado --«salieron 48 jugadores donde la plantilla tiene 25»-- y se
    repitió aquí el 2026-10-27 al escribir la consulta en plural. Lo cazó el
    usuario leyendo un número de más en una frase mía.
    """
    jugadores = (
        (
            await session.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id,
                    m.Player.left_team_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    pares: list[tuple[m.Player, m.PlayerSnapshot]] = []
    for jugador in jugadores:
        foto = (
            await session.execute(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == jugador.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if foto is not None:
            pares.append((jugador, foto))
    return pares


async def _series_de_la_plantilla(
    session: AsyncSession, team_id: int, convertido: Callable[[int], int]
) -> dict[int, tuple[int, ...]]:
    """Las medias pasadas de cada jugador, en una sola consulta.

    Mismo corte por tramo vigente que `_serie` --cuando a un jugador le
    cambian los criterios su historia vuelve a empezar-- pero para todos a la
    vez: la tabla sólo necesita la línea, no cada nube.
    """
    filas = (
        (
            await session.execute(
                select(m.MarketEstimate)
                .where(m.MarketEstimate.team_id == team_id)
                .order_by(m.MarketEstimate.ht_player_id, m.MarketEstimate.captured_at)
            )
        )
        .scalars()
        .all()
    )
    por_jugador: dict[int, list[m.MarketEstimate]] = {}
    for fila in filas:
        por_jugador.setdefault(fila.ht_player_id, []).append(fila)

    series: dict[int, tuple[int, ...]] = {}
    for ht_player_id, lecturas in por_jugador.items():
        vigente = lecturas[-1].criteria_key
        corte = len(lecturas)
        while corte > 0 and lecturas[corte - 1].criteria_key == vigente:
            corte -= 1
        medias = [
            convertido(lectura.mean_price)
            for lectura in lecturas[corte:]
            if lectura.mean_price is not None
        ]
        if medias:
            series[ht_player_id] = tuple(medias)
    return series


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

    SÓLO EL TRAMO VIGENTE (2026-10-26, decisión del usuario: cuando le cambian
    los criterios, «la gráfica de precios volverá a empezar»). Los criterios
    son del jugador y Hattrick los recalcula con él --al cumplir años, al subir
    una habilidad-- y desde ese momento el barrido pregunta por otra gente. Dos
    medidas distintas unidas por una línea dibujarían una subida o una bajada
    que no ocurrió.

    El corte se hace aquí y no borrando: los puntos de los tramos anteriores
    siguen en la tabla. Es la única pérdida de esta base que no se podría
    deshacer, porque el fondo no sabe cómo estuvo.
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
    # El tramo vigente es el del ÚLTIMO punto, y se corta hacia atrás: en
    # cuanto aparece una clave distinta, lo anterior es otra medida. Se recorre
    # al revés porque lo que define el tramo es el final, no el principio.
    if filas:
        vigente = filas[-1].criteria_key
        corte = len(filas)
        while corte > 0 and filas[corte - 1].criteria_key == vigente:
            corte -= 1
        filas = filas[corte:]

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
