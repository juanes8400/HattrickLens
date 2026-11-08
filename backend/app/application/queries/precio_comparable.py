"""Lo que ha costado la gente parecida a un jugador tuyo, para la pantalla.

No llama a Hattrick ni una vez: todo sale del fondo que dejó el paso del mercado,
así que abrir la ficha de un jugador es gratis y se puede recalcular tantas
veces como haga falta. Por eso tampoco hay nada que invalidar cuando el jugador
sube una habilidad o cumple años: sus comparables se vuelven a medir contra el
jugador de hoy y los que dejan de parecerse se caen solos.

LA LISTA ES SOLO DE VENTAS CERRADAS (2026-11-07, decisión del usuario: «los
jugadores que nunca se vendieron, no deben ir en la lista»). Hasta hoy viajaban
también las subastas vivas y los anuncios a cero, marcados; la tabla tenía
entonces tres columnas que sólo servían para decir por qué una fila no traía
precio --«sin confirmar», «NO PUJA DETECTADA», «cierra en 11 h»-- y las filas
sin precio eran la mayoría desde que el barrido se hizo diario.

Lo que no se enseña no se pierde: sigue en el fondo, se sigue vigilando y
`provisionales` dice cuántas hay esperando su precio. Lo que se deja de hacer es
ponerlas delante de las ventas de verdad.

Lo que la pantalla está obligada a decir, y por eso viaja aquí:

· **Cuántas subastas siguen abiertas.** Esperan su precio y no promedian: una
  puja se queda corta, y el 2026-10-05 Valerio Cataldi tenía 65.000.000 de puja
  y cerró en 77.720.000, un 16% más.
· **De cuándo es lo más viejo.** Una venta sigue contando pasadas sus
  veinticuatro semanas si no apareció nada mejor, y entonces el número habla de
  un mercado que puede haber cambiado.
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
from app.domain.engines.criterios_hattrick import criterios_de
from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    PESO_DEL_CLAVADO,
    VIDA,
    Guardado,
    Objetivo,
    comparables_de,
    estimar,
    nunca_tuvo_puja,
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
    #: Si ya se vendió de verdad. En la lista de comparables es SIEMPRE cierto
    #: desde el 2026-11-07 --es lo que define la lista-- y sólo la fila del
    #: jugador propio lo trae en falso: él no está en venta.
    firme: bool
    #: AQUÍ VIVÍA `cuenta`, «si entra en el número», y se fue el 2026-11-07 con
    #: las filas que no se vendieron: valía `venta.firme` y nadie lo leía ya.
    viejo: bool
    edad: int
    #: Los DÍAS de su edad, además de los años (2026-11-07, pedido del
    #: usuario: el Comparador de Transferencias del juego los enseña, y a los
    #: 17 años son parte de la regla). `-1` es «no los sabemos»: las ventas
    #: anotadas antes de la migración 0103.
    dias: int
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
    #: Su FORMA, de 1 a 8. Columna del Comparador de Transferencias que el
    #: usuario pidió el 2026-11-07. `-1` es «no la sabemos»: toda venta
    #: anotada antes de la migración 0112.
    forma: int
    #: Lo que PEDÍA el vendedor cuando se encontró el anuncio. Cero es «no lo
    #: sabemos». NO es un precio: es lo que una persona decidió pedir, y por
    #: eso no entra en ninguna media. Se enseña al lado del que se pagó
    #: porque la distancia entre los dos es el dato.
    precio_pedido: int
    #: Si en ningún momento vimos una puja sobre este anuncio. Es la columna
    #: «NO PUJA DETECTADA»: en una venta ya cerrada dice que la subasta se
    #: movió entre dos barridos nuestros, que es lo que pasó con el 472301981.
    sin_puja: bool
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
    #: AQUÍ VIVÍAN `dial_holgado`, `rareza` y `liston`, y se fueron el
    #: 2026-11-04 por decisión del usuario: «quita este tipo de mensajes, ya
    #: que no aportan nada y son información del algoritmo».
    #:
    #: Eran los tres números con los que la pantalla explicaba por qué la
    #: búsqueda salía ancha --«su rareza es 35 y el listón que le toca 23»--.
    #: La pregunta que esta pantalla contesta es CON QUÉ buscó Hattrick, y eso
    #: son los criterios de arriba; la rareza y el listón son nuestra cocina.
    #: Quitada la frase, los tres campos no los pintaba nadie, así que se van
    #: también del DTO en vez de quedarse viajando por si acaso.
    #:
    #: El motor NO pierde nada: `es_holgado`, `rareza` y `liston_de` siguen en
    #: `criterios_hattrick`, con sus 639 casos medidos, y el dial sigue
    #: decidiendo la forma de los criterios. Lo que se deja de hacer es
    #: enseñarlo.
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
        # LA MÁS VIEJA DE LAS QUE CUENTAN, que es lo que esta línea decía que
        # hacía y no hacía (2026-11-07). Se medía sobre `elegidos` entero, así
        # que un anuncio a cero de hace cinco meses ponía la pastilla en «la
        # más vieja, de hace 20 sem» mientras la venta más vieja de la tabla
        # era de hace tres. Desde que esas filas no se enseñan, el desajuste
        # sería invisible y además indiscutible: no quedaría fila que lo
        # desmintiera.
        semanas_del_mas_viejo=max(
            (_semanas(c.venta.visto_el, momento) for c in elegidos if c.venta.firme),
            default=0,
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
            viejo=False,
            edad=foto.age_years or 0,
            dias=foto.age_days if foto.age_days is not None else -1,
            perfil=_perfil(objetivo),
            semanas=0,
            cierra=None,
            especialidad=SPECIALTIES.get(foto.specialty or 0, ""),
            tsi=foto.tsi or 0,
            forma=foto.form if foto.form is not None else -1,
            # Tu jugador no está en venta: no pide precio y nadie le ha pujado.
            # Un cero aquí se leería como «vale cero», que es lo contrario de
            # lo que dice, así que `sin_puja` queda en falso para que la
            # pantalla no le ponga el sello de «NO PUJA DETECTADA».
            precio_pedido=0,
            sin_puja=False,
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
                peso=c.peso,
                avalado_por_hattrick=c.avalado_por_hattrick,
                firme=c.venta.firme,
                viejo=c.viejo,
                edad=c.venta.edad,
                dias=c.venta.dias,
                perfil=_perfil(c.venta),
                semanas=_semanas(c.venta.visto_el, momento),
                # EL PLAZO SALE DE LA VENTA, no de un diccionario por jugador
                # (2026-11-07). Desde la migración 0105 un mismo jugador puede
                # tener DOS subastas --el 490357848 sale dos veces en su propio
                # Comparador, a 215.220 y a 125.000-- y una clave `{jugador:
                # plazo}` se quedaba con el plazo de una de las dos y lo pegaba
                # a las dos filas. Importa más desde hoy, porque ese plazo es
                # también la columna «Fecha».
                cierra=c.venta.plazo,
                especialidad=SPECIALTIES.get(c.venta.especialidad, ""),
                tsi=c.venta.tsi,
                forma=c.venta.forma,
                precio_pedido=convertido(c.venta.precio_pedido),
                sin_puja=nunca_tuvo_puja(c.venta),
                pais_codigo=paises.get(c.venta.pais, ("", ""))[0],
                pais_nombre=paises.get(c.venta.pais, ("", ""))[1],
            )
            # SÓLO LO QUE SE VENDIÓ (2026-11-07, decisión del usuario: «los
            # jugadores que nunca se vendieron, no deben ir en la lista»).
            #
            # `elegidos` sigue trayéndolas todas, y hace falta que las traiga:
            # `estimar` cuenta sobre ellas las subastas abiertas, y el motor
            # necesita saber qué plazas están ocupadas para no salir a buscar
            # de más. Lo que cambia es qué se PINTA.
            #
            # El corte es `venta.firme` y no `c.cuenta` a propósito, aunque hoy
            # valen lo mismo: lo que el usuario pidió es «que se haya vendido»,
            # no «que entre en la media». Si algún día una venta cerrada
            # dejara de promediar, seguiría siendo una venta y seguiría
            # mereciendo su fila.
            for c in elegidos
            if c.venta.firme
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
    #: CUÁNTOS DE LA PLANTILLA NO SALEN EN `jugadores`, y por qué existe este
    #: número (2026-11-04, lo cazó una revisión automática del PR #23).
    #:
    #: Esta consulta deja fuera, en silencio, a dos clases de jugador: al que
    #: todavía no tiene ni una foto --sin habilidades no hay terna, y sin terna
    #: no hay a quién parecerse-- y a aquél del que no se puede sacar una terna
    #: o una edad. Mientras lo único que se enseñaba era una fila por jugador,
    #: faltar no se notaba. Pero la pantalla de Valoración SUMA, y dice «de X de
    #: Y jugadores»: si ese `Y` sale de contar las filas devueltas, una
    #: plantilla de treinta con tres sin foto se anuncia como una de
    #: veintisiete, y nadie puede verlo.
    #:
    #: Con esto, quien suma puede decir la verdad: cuántos cuentan, cuántos no
    #: tienen comparables todavía, y cuántos ni siquiera se han podido medir.
    sin_medir: int = 0


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
    pares, en_plantilla = await _plantilla_con_foto(session, team_id)
    for jugador, foto in pares:
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
                # De las que CUENTAN, igual que en la ficha: las dos pantallas
                # enseñan el mismo número del mismo jugador.
                semanas_del_mas_viejo=max(
                    (_semanas(c.venta.visto_el, momento) for c in elegidos if c.venta.firme),
                    default=0,
                ),
                serie=series.get(jugador.ht_player_id, ()),
            )
        )
    # Lo que falta es la plantilla MENOS las filas que han salido, así que
    # recoge las dos puertas de salida de una vez: el que no tiene foto y aquél
    # del que no se pudo sacar una terna.
    return PreciosDeLaPlantilla(
        moneda=moneda,
        jugadores=tuple(filas),
        sin_medir=max(0, en_plantilla - len(filas)),
    )


async def _plantilla_con_foto(
    session: AsyncSession, team_id: int
) -> tuple[list[tuple[m.Player, m.PlayerSnapshot]], int]:
    """La plantilla DE HOY, con la foto más reciente de cada jugador.

    Devuelve también CUÁNTOS SON EN TOTAL, incluidos los que se quedan fuera.
    Quien suma necesita ese número para no anunciar como plantilla entera lo
    que es sólo la parte medible; ver `PreciosDeLaPlantilla.sin_medir`.

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
    return pares, len(jugadores)


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
