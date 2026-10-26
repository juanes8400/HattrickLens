"""Distinguir «no hay nadie» de «Hattrick no nos está contestando».

2026-10-25. Nace para poder medir precios TODOS LOS DÍAS --decisión del
usuario-- y nace antes que el barrido porque es lo que decide si el barrido se
puede hacer.

EL PELIGRO, MEDIDO. El 2026-10-12, sondeando el Comparador del juego:

    «Hattrick se agoto: de cinco peticiones seguidas, UNA traia criterios y
    cuatro volvian vacias.»

Lo grave no es quedarse sin cuota: es que **quedarse sin cuota no da error**.
La respuesta llega bien formada, con cero resultados, idéntica a la de un
jugador al que de verdad nadie se parece. `BusquedaRechazadaError` cubre el
«no» explícito de Hattrick; esto cubre el silencio, que es el caso que de
verdad pasó.

QUÉ SE PIERDE SI NO SE DISTINGUE. No el fondo: una búsqueda vacía no guarda
nada, así que un día sin cuota no mete comparables falsos. Se pierden dos
cosas peores de lo que parecen:

  · EL DÍA. El barrido es una vez por día natural y por jugador, así que si se
    da por hecho con la cuota muerta, ese día del mercado no vuelve.
  · LA CUOTA DE TODOS. Es de la aplicación, no de cada manager. Insistir ciento
    veinte veces contra un servidor que no contesta es lo que la mantiene
    muerta para el resto.

CÓMO SE DISTINGUE. Por la respuesta no se puede: son iguales. Preguntando otra
cosa, sí. Si no nos están contestando, también viene vacía una búsqueda que el
mercado no puede tener vacía nunca.

De ahí las dos piezas:

  · EL CANARIO cuesta una petición y responde del todo. Se le pide al mercado
    algo anchísimo y corriente --`canario()`--: si eso vuelve vacío, no es que
    no haya nadie. Va al principio del barrido, antes de gastar las ciento
    veinte, y vuelve a ir cuando la racha lo pide.
  · LA RACHA no cuesta nada y sólo levanta la sospecha. Un vacío es de lo más
    normal --la ventana exacta de un jugador raro no tiene a nadie casi
    nunca-- así que el umbral no vigila vacíos: vigila que se acumulen.

Y EL UMBRAL SE DOBLA cada vez que el canario DESMIENTE UNA RACHA. Si no se
doblara, un barrido de plantilla rara pagaría un canario cada seis jugadores;
doblándose, ciento veinte búsquedas caben en cuatro canarios como mucho. Cada
desmentido es además mejor prueba que el anterior: a la tercera vez que el
mercado contesta, que el siguiente vacío sea de verdad ya no es una suposición.

El de apertura NO dobla, y la distinción importa. No ha desmentido nada --no
hay racha todavía-- así que si contara, la primera sospecha del barrido
necesitaría doce vacíos en vez de seis y una cuota muerta a mitad tardaría el
doble en notarse. El doblado es el premio por haber tumbado una sospecha, no
por haber contestado una vez.

EL REPARTO DEL DAÑO ES A PROPÓSITO. Equivocarse hacia «agotada» cuesta un día
y se reintenta mañana. Equivocarse hacia «sigue» gasta la cuota de todos en
balde y da el día por medido sin medirlo. Así que ante la duda, PARAR.

Y nótese que todas las razones por las que el canario podría callarse --cuota
agotada, Hattrick caído, la credencial caducada, el fichero del mercado
cambiado de forma-- son razones para parar. No hay ninguna que aconseje
seguir, y eso es lo que hace que un canario mudo se pueda creer sin más
pruebas.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engines.mercado_comparable import Franja, Ventana

#: Vacíos seguidos que hacen sospechar la primera vez. Seis, elegido y no
#: medido: es la cuarta parte de una plantilla, así que una plantilla entera
#: cabe en cuatro sospechas. Ver abajo por qué se dobla.
RACHA_INICIAL = 6

#: Una búsqueda no puede tener más de cuatro niveles en el primer filtro
#: --regla del servidor, comprobada el 2026-10-05-- así que el canario pide
#: justo cuatro: el tramo más ancho que se puede pedir de una vez.
TRAMO_DEL_CANARIO = (5, 8)

#: La franja de edad del canario. No la más ancha posible sino la más poblada:
#: lo que se quiere es que no pueda estar vacía, no que entre todo el mundo.
EDAD_DEL_CANARIO = (17, 30)


def canario() -> Ventana:
    """Una búsqueda que el mercado no puede tener vacía.

    Defensa entre cinco y ocho, de diecisiete a treinta años, y las otras dos
    habilidades sin pedir nada: es el medio del mercado, donde está casi todo
    el mundo. En el mercado mundial hay miles de anuncios a cualquier hora, y
    esto se lleva una tajada enorme de ellos.

    EL PESO ES CERO Y NO SE USA. El canario no alimenta el fondo: lo que trae
    se cuenta y se tira. Darle un peso de la escalera invitaría a guardarlo, y
    guardarlo sería meter en el fondo gente que no se parece a nadie nuestro.
    """
    desde, hasta = TRAMO_DEL_CANARIO
    joven, viejo = EDAD_DEL_CANARIO
    return Ventana(
        peso=0,
        edad_minima=joven,
        edad_maxima=viejo,
        primaria=Franja(habilidad="defending", minimo=desde, maximo=hasta),
        secundaria=Franja(habilidad="playmaking", minimo=0, maximo=20),
        terciaria=Franja(habilidad="scoring", minimo=0, maximo=20),
    )


@dataclass(slots=True)
class Centinela:
    """Lleva la cuenta de los vacíos de un barrido y dice cuándo parar.

    No hace peticiones ni sabe hacerlas: se le cuenta lo que trajo cada
    búsqueda y él contesta. Quien lo use se encarga de preguntarle al canario
    cuando lo pida.
    """

    #: Vacíos seguidos que hacen falta para la próxima sospecha.
    umbral: int = RACHA_INICIAL
    #: Vacíos seguidos ahora mismo.
    racha: int = 0
    vacias: int = 0
    llenas: int = 0
    #: Canarios gastados, que es lo que este aparato cuesta.
    canarios: int = 0
    agotada: bool = False

    @property
    def sigue(self) -> bool:
        """Si el barrido puede continuar."""
        return not self.agotada

    @property
    def hay_que_preguntar(self) -> bool:
        """Si toca gastar una petición en el canario antes de seguir.

        También es cierto al empezar, con cero búsquedas hechas: el canario del
        principio es el que evita gastar ciento veinte peticiones contra un
        servidor que no contesta.
        """
        if self.agotada:
            return False
        if self.canarios == 0:
            return True
        return self.racha >= self.umbral

    def vio(self, cuantos: int) -> None:
        """Anota lo que trajo una búsqueda.

        Se cuentan RESULTADOS y no comparables: lo que mide esto es si el
        servidor contesta, y un jugador que llega y luego se descarta por no
        parecerse demuestra que contestó igual de bien que uno que se queda.
        """
        if cuantos > 0:
            self.llenas += 1
            self.racha = 0
            return
        self.vacias += 1
        self.racha += 1

    def canto_el_canario(self, cuantos: int) -> None:
        """El resultado del canario: con gente canta, vacío calla.

        Si canta, los vacíos de antes eran de verdad y la racha se perdona. Si
        calla, el barrido se acabó --`sigue` pasa a falso-- y no se vuelve a
        preguntar: un canario mudo ya es toda la prueba que hay.
        """
        self.canarios += 1
        if cuantos <= 0:
            self.agotada = True
            return
        # Sólo dobla si había algo que desmentir. El canario de apertura no
        # desmiente nada, y dejarle doblar retrasaría al doble la primera
        # sospecha del barrido.
        if self.racha > 0:
            self.umbral *= 2
        self.racha = 0
