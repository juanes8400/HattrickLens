"""Los criterios que Hattrick usa en su Comparador de Transferencias.

QUÉ ES ESTO. Dado un jugador --edad y sus siete habilidades-- devuelve la lista
de criterios con la que Hattrick buscaría ventas parecidas. No es nuestra idea
de «parecido»: es la suya, reproducida.

DE DÓNDE SALE. De preguntárselo al juego. El Comparador tiene un panel «Editar
búsqueda» que acepta un perfil cualquiera --edad y las siete habilidades, exista
el jugador o no-- y devuelve los criterios que él mismo calcula. El 2026-10-10 se
sondeó con unas 520 consultas de perfiles sintéticos, moviendo un eje cada vez y
buscando por bisección dónde salta cada regla. Los datos crudos están en
`docs/reference/sondeo-comparador/`, y la procedencia y el método en
`docs/reference/CRITERIOS_DEL_COMPARADOR.md`.

CUÁNTO SE LE CREE. Las pruebas de `test_criterios_hattrick.py` fijan 55 casos
contra lo que contestó Hattrick, no contra este módulo. Quince de esos casos se
predijeron A CIEGAS --la regla escrita primero, la consulta después-- y acertaron
los quince, en una tanda de perfiles que el modelo no había visto nunca. Antes de
eso, la misma prueba ciega daba 8 de 15: cada fallo está anotado en los datos
crudos junto a la regla que lo arregló, porque saber por dónde falló importa
tanto como la regla.

POR QUÉ ASÍ Y NO AJUSTANDO. `AGENTS.md` prohíbe sacar fórmulas ajustándolas
contra la plantilla del propietario. Aquí no se ajusta nada: se le pregunta la
regla al juego, que es la fuente general que esa norma exige, y los perfiles
sondeados son inventados. Los jugadores propios sólo sirvieron para abrir la
página.

QUÉ NO SE SABE. Está marcado en el código con `DESCONOCIDO`. Lo que no se
sondeó no se extrapola.

CADUCIDAD. Hattrick cambió este comparador al menos una vez sin publicar qué
--temporada 69, 30 de julio de 2018-- y la única explicación oficial que existe
es de 2009 y ya estaba desfasada cuando la leímos. Esta tabla puede quedarse
vieja igual. Por eso se guarda la fecha del sondeo y los datos en bruto: para
poder repetirlo y comparar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Las seis habilidades de campo, en el orden en que Hattrick decide DE QUÉ
#: TIPO es el jugador cuando dos valen lo mismo.
#:
#: Se midió por eliminación: las seis a 12 y se mira cuál manda; se pone a cero
#: la ganadora y se repite. Salió Lateral, Anotación, Portería, Defensa,
#: Jugadas, Pases. Confirma dos casos sueltos que ya chirriaban: con Portería
#: 11 y Defensa 11 elige portero, y con Defensa 12 y Jugadas 12 elige defensa.
ORDEN_LLANO: tuple[str, ...] = (
    "winger",
    "scoring",
    "keeper",
    "defending",
    "playmaking",
    "passing",
)

#: Balón parado. Sólo entra en la plantilla del portero: se comprobó que un
#: jugador de campo con 0, con 12 y con 20 recibe criterios idénticos.
BALON_PARADO = "set_pieces"

#: La plantilla de cada tipo de jugador: qué habilidades mira Hattrick y en qué
#: orden las desempata. El tipo lo da la habilidad dominante.
#:
#: Se midió dos veces, con el resto del perfil a 0 y con el resto a 10, y salió
#: el mismo orden las dos veces: la plantilla depende sólo de quién domina.
PLANTILLAS: dict[str, tuple[str, ...]] = {
    "keeper": ("keeper", "defending", BALON_PARADO, "winger", "scoring", "playmaking"),
    "defending": ("defending", "passing", "playmaking", "winger", "scoring", "keeper"),
    "playmaking": ("playmaking", "passing", "defending", "winger", "scoring", "keeper"),
    "winger": ("winger", "playmaking", "passing", "defending", "scoring", "keeper"),
    "passing": ("winger", "passing", "playmaking", "defending", "scoring", "keeper"),
    "scoring": ("scoring", "passing", "winger", "playmaking", "defending", "keeper"),
}

#: La habilidad que da el tipo va SIEMPRE la primera, aunque otra tenga más
#: nivel. Sólo se nota en el pasador: con Pases 16 y todo lo demás a cero, el
#: primer criterio es «Lateral = nulo». Clavar el Lateral es lo que separa a un
#: pasador de un extremo de verdad.

#: Por debajo de esto, una habilidad no es criterio de identidad: cae al montón
#: de los techos. El segundo puesto entra antes que el tercero, y el portero
#: antes que nadie: a su Defensa le basta un 2 donde al resto le hacen falta 3.
#: El techo que le ponen mientras no entra es siempre la entrada menos uno.
ENTRADA_SEGUNDO = 3
ENTRADA_SEGUNDO_PORTERO = 2
ENTRADA_TERCERO = 5

#: A partir de aquí el tercer puesto deja de ser banda y pasa a ser suelo.
SUELO_DEL_TERCERO = 11

#: Y a partir de aquí el CUARTO puesto cambia de banda estrecha a banda ancha.
CUARTO_CON_BANDA_ANCHA = 8

#: El segundo puesto deja de ir clavado si él mismo llega aquí...
#: Y el portero, otra vez, mucho antes: su Defensa va clavada hasta 6 y con
#: banda desde 7, barrido entero del 1 al 9.
SEGUNDO_CON_BANDA = 10
SEGUNDO_CON_BANDA_PORTERO = 7
#: ...o si el tercero llega aquí. Lo decía ya el texto de 2009: «lo mismo
#: ocurre si la tercera es alta». El umbral son siete, y eso no lo decía.
TERCERO_QUE_ABRE_AL_SEGUNDO = 7

#: Balón parado del portero: banda ancha hasta 15, y de 16 en adelante un suelo
#: fijo que no depende del nivel. La anchura sigue al dial, como todo lo demás:
#: con balón parado 9, un portero holgado recibe 6-12 y uno ajustado 7-11.
BP_BANDA_MAXIMA = 15
BP_SUELO_FIJO = 14
BP_SEMIANCHO_HOLGADO = 3
BP_SEMIANCHO_AJUSTADO = 2

#: EL DIAL. Hattrick afloja toda la búsqueda a la vez --la edad, la anchura del
#: tercer puesto y los techos-- cuando el jugador es raro, que es lo que
#: declararon en 2009: buscar el equilibrio entre precisión y resultados
#: suficientes.
#:
#: La medida se despejó de las parejas frontera. Para la primera y la segunda
#: cuenta el nivel entero; de la tercera en adelante, sólo lo que pase de seis.
#: Y sólo cuentan las cuatro primeras: con seis habilidades a 9 sigue ajustado.
#:
#: Cuentan LAS HABILIDADES DE SU PLANTILLA, no las seis de campo. Importa en el
#: portero por los dos lados: su balón parado SÍ entra --con Portería 12 y
#: Defensa 8, pasar el balón parado de 0 a 15 abre la búsqueda-- mientras que
#: el balón parado de un jugador de campo no cambia absolutamente nada.
#: El umbral NO es el mismo para todos. Medido con la primera clavada en 14 y
#: barriendo la segunda: extremo, delantero y medio saltan los tres en 27,
#: mientras que el defensa salta en 25 --comprobado con Jugadas y con Pases de
#: segunda, para descartar que fuera la habilidad y no el tipo-- y el portero
#: en 21. Tiene sentido: cuanto más raro es el puesto, antes hay que ensanchar.
UMBRAL_POR_TIPO: dict[str, int] = {
    "keeper": 21,
    "defending": 25,
    "playmaking": 27,
    "winger": 27,
    "passing": 27,
    "scoring": 27,
}
#: Una primera habilidad de 17 afloja ella sola, con segunda o sin ella.
PRIMERA_QUE_AFLOJA_SOLA = 17
#: Y CON LAS DOS PRIMERAS EMPATADAS el umbral baja a 25, sea el tipo que sea.
#: Medido con Lateral y Anotación a la par: rareza 25 afloja y 24 no, mientras
#: que el mismo extremo con la segunda por debajo necesitaba 27. Tiene sentido:
#: un jugador con dos habilidades iguales arriba encaja en menos moldes.
UMBRAL_CON_EMPATE_ARRIBA = 25
#: El balón parado del portero cuenta para la rareza, pero descontándole más
#: que a una habilidad normal: con Portería 14 y Defensa 6, un balón parado de
#: 9 deja la búsqueda ajustada y uno de 15 la abre.
DESCUENTO_DEL_BALON_PARADO = 10
#: HASTA AQUÍ NO HAY DIAL QUE VALGA. El mismo perfil --Defensa 17, Jugadas 3--
#: sale ajustado a los 19, 20 y 21 y holgado a los 22 y 25. No es que la edad
#: tenga su propia regla: es que al jugador joven le aprietan TODA la búsqueda.
EDAD_QUE_APRIETA_TODO = 21
DESCUENTO_DESDE_LA_TERCERA = 6
HABILIDADES_QUE_CUENTAN = 4

#: Y de viejo se abre la edad AUNQUE el resto siga ajustado: a los 32, con un
#: perfil ajustado, la edad sale 31-33 pero los techos siguen en 4 y la banda
#: de la tercera sigue midiendo tres.
EDAD_SIEMPRE_ABIERTA = 32
#: A los 17, y sólo a los 17, Hattrick añade un tope de días. No se pudo
#: estudiar: el panel no tiene campo de días. DESCONOCIDO de dónde sale el 24.
EDAD_CON_TOPE_DE_DIAS = 17
TOPE_DE_DIAS_OBSERVADO = 24

Operador = Literal["=", "banda", ">=", "<="]


@dataclass(frozen=True, slots=True)
class Criterio:
    """Un criterio de habilidad, tal y como lo pinta la pantalla.

    `minimo` y `maximo` siempre están rellenos para que quien lo use no tenga
    que mirar el operador: un `>=` trae el máximo al tope de la escala y un
    `<=` trae el mínimo a cero. El operador se conserva para poder enseñar el
    criterio con las mismas palabras que Hattrick.
    """

    habilidad: str
    operador: Operador
    minimo: int
    maximo: int

    def admite(self, nivel: int) -> bool:
        return self.minimo <= nivel <= self.maximo


@dataclass(frozen=True, slots=True)
class Criterios:
    """La búsqueda entera: la ventana de edad y los criterios de habilidad."""

    edad_minima: int
    edad_maxima: int
    habilidades: tuple[Criterio, ...]
    #: Si el jugador cayó del lado holgado del dial. Se expone porque explica
    #: por qué la búsqueda salió ancha, y eso hay que poder enseñarlo.
    holgado: bool
    #: El tope de días, sólo a los 17 años. `None` en cualquier otro caso.
    tope_de_dias: int | None = None


MAXIMO_DE_LA_ESCALA = 20


def _tipo(niveles: dict[str, int]) -> str:
    """La habilidad dominante, que es la que elige la plantilla.

    CON UNA EXCEPCIÓN: Hattrick no tiene puesto de pasador. Cuando lo que más
    tiene el jugador son Pases, el tipo lo decide la MEJOR DE LAS DEMÁS --un
    Pases 15 con Jugadas 12 y Lateral 9 se trata como mediocentro, y sus
    criterios empiezan por «Jugadas = magnífico»--. Si no tiene ninguna otra,
    cae en extremo, que es el primero del desempate.
    """
    mejor = min(ORDEN_LLANO, key=lambda h: (-niveles.get(h, 0), ORDEN_LLANO.index(h)))
    if mejor != "passing":
        return mejor
    resto = [h for h in ORDEN_LLANO if h != "passing"]
    return min(resto, key=lambda h: (-niveles.get(h, 0), resto.index(h)))


def rareza(niveles: dict[str, int], tipo: str | None = None) -> int:
    """La medida que mueve el dial.

    La primera y la segunda cuentan enteras; de la tercera en adelante sólo lo
    que pasa de seis, y sólo cuentan cuatro habilidades. Es la fórmula que
    reproduce las parejas frontera medidas: (16,9) afloja y (16,8) no; (13,12)
    afloja y (12,12) no; (14,10,7) afloja y (14,10,6) no.
    """
    tipo = tipo or _tipo(niveles)
    plantilla = PLANTILLAS[tipo]
    pesados = []
    for h in plantilla:
        nivel = max(0, niveles.get(h, 0))
        if h == BALON_PARADO:
            nivel = max(0, nivel - DESCUENTO_DEL_BALON_PARADO + DESCUENTO_DESDE_LA_TERCERA)
        pesados.append(nivel)
    v = sorted(pesados, reverse=True)
    v += [0] * (HABILIDADES_QUE_CUENTAN - len(v))
    total = v[0] + v[1]
    for nivel in v[2:HABILIDADES_QUE_CUENTAN]:
        total += max(0, nivel - DESCUENTO_DESDE_LA_TERCERA)
    return total


def es_holgado(niveles: dict[str, int], tipo: str | None = None, edad: int | None = None) -> bool:
    """Si la búsqueda sale en modo ancho.

    La segunda condición es aparte y no es redundante: una habilidad de 17 ya
    hace raro al jugador ella sola. Se vio con (17,5), que afloja con una
    rareza de sólo 22, y con (18,0), que afloja sin segunda habilidad. Vale
    también para el portero: Portería 15 sola no abre, Portería 17 sí.

    Y las dos primeras empatadas bajan el listón a 25: un extremo con Lateral y
    Anotación a 12 y Pases 7 --rareza 25-- afloja, mientras que el mismo extremo
    con la segunda por debajo aguantaba hasta 27.
    """
    if edad is not None and edad <= EDAD_QUE_APRIETA_TODO:
        return False
    tipo = tipo or _tipo(niveles)
    v = sorted((max(0, niveles.get(h, 0)) for h in PLANTILLAS[tipo]), reverse=True)
    umbral = UMBRAL_POR_TIPO[tipo]
    if len(v) > 1 and v[0] == v[1]:
        umbral = min(umbral, UMBRAL_CON_EMPATE_ARRIBA)
    return rareza(niveles, tipo) >= umbral or v[0] >= PRIMERA_QUE_AFLOJA_SOLA


def _ventana_de_edad(edad: int, holgado: bool) -> tuple[int, int]:
    if edad <= EDAD_QUE_APRIETA_TODO:
        return edad, edad
    if edad >= EDAD_SIEMPRE_ABIERTA or holgado:
        return edad - 1, edad + 1
    return edad, edad


#: Cuántos puestos identifican al jugador. Los demás sólo le ponen tope.
#:
#: SON TRES, O CUATRO si la cuarta habilidad también pasa del umbral de entrada.
#: Se vio con un extremo de Lateral 10, Pases 9, Jugadas 6 y Defensa 6: le
#: salieron CUATRO criterios de identidad --«Lat=10 Pas 8-10 Jug 5-7 Def 5-7»--
#: en vez de tres y un techo. Es la «cuartil» que nombraba el texto de 2009.
PUESTOS_DE_IDENTIDAD = 3


def _puestos(niveles: dict[str, int], tipo: str) -> list[str]:
    """Las habilidades ordenadas como las ordena Hattrick.

    LOS TRES PRIMEROS se llenan POR VALOR descendente, y cuando dos empatan
    manda la plantilla: con Defensa 16, Jugadas 8 y Pases 8 el segundo
    criterio fue Pases, que va antes en la plantilla del defensa; con Pases 0
    en vez de 8, el segundo fue Jugadas.

    LOS TRES ÚLTIMOS van en orden de plantilla y no por valor. Se ve en
    Ebbesen, cuyos sobrantes son Lateral 1, Anotación 3 y Jugadas 2 y salen
    listados Lateral, Anotación, Jugadas --el orden de la plantilla del
    portero-- y no de mayor a menor.

    EL PORTERO no reordena nada: sus tres primeros son siempre Portería,
    Defensa y Balón parado. Con Portería 12 y balón parado 15, el balón
    parado siguió tercero en vez de adelantar.
    """
    plantilla = PLANTILLAS[tipo]
    if tipo == "keeper":
        return list(plantilla)

    def clave(h: str) -> tuple[int, int, int]:
        # ADELANTAR CUESTA. Una habilidad sólo pasa por delante de otra si le
        # saca tantos niveles como puestos las separan en la plantilla. Medido:
        # con Pases 7, Jugadas --que va justo detrás-- adelanta con 8, pero
        # Lateral --dos puestos más atrás-- necesita 9. Con Pases 10, Lateral
        # necesita 12. Con Pases 3, Lateral necesita 5. Siempre la distancia.
        #
        # Es la regla que flameron describió en 2009 sin dar el número, y la
        # que a mí se me escapó: barriendo un eje cada vez nunca aparece.
        pos = plantilla.index(h)
        return (-(niveles.get(h, 0) - pos), -niveles.get(h, 0), pos)

    ordenadas = sorted(plantilla, key=clave)
    cuantos = PUESTOS_DE_IDENTIDAD
    if len(ordenadas) > cuantos and niveles.get(ordenadas[cuantos], 0) >= ENTRADA_TERCERO:
        cuantos += 1
    cabeza = ordenadas[:cuantos]
    if cabeza[0] != tipo:
        if tipo in cabeza:
            cabeza.remove(tipo)
        else:
            cabeza.pop()
        cabeza.insert(0, tipo)
    return cabeza + [h for h in plantilla if h not in cabeza]


def _techo_de_sobrante(nivel: int, holgado: bool) -> int:
    """El tope de las habilidades que no identifican al jugador.

    Hasta 4 el techo es FIJO --4 ajustado, 5 holgado-- y de 5 en adelante sigue
    al nivel. Medido en holgado con 0, 2 y 4 (todos a 5) y con 5, 8 y 12 (a 7,
    10 y 14, o sea nivel + 2). En ajustado sólo hay el tramo fijo y un punto
    suelto arriba, el perfil plano a nivel 5, que dio nivel + 1.
    """
    if nivel < ENTRADA_TERCERO:
        return 5 if holgado else 4
    return nivel + (2 if holgado else 1)


def _balon_parado(nivel: int, holgado: bool) -> Criterio:
    if nivel < ENTRADA_TERCERO:
        return Criterio(BALON_PARADO, "<=", 0, _techo_de_sobrante(nivel, holgado))
    if nivel > BP_BANDA_MAXIMA:
        return Criterio(BALON_PARADO, ">=", BP_SUELO_FIJO, MAXIMO_DE_LA_ESCALA)
    ancho = BP_SEMIANCHO_HOLGADO if holgado else BP_SEMIANCHO_AJUSTADO
    return Criterio(BALON_PARADO, "banda", max(0, nivel - ancho), nivel + ancho)


def criterios_de(edad: int, niveles: dict[str, int]) -> Criterios:
    """Los criterios con los que Hattrick buscaría parecidos a este jugador.

    `niveles` lleva las seis de campo y, si se tiene, `set_pieces`. Lo que
    falte cuenta como cero.
    """
    tipo = _tipo(niveles)
    holgado = es_holgado(niveles, tipo, edad)
    orden = _puestos(niveles, tipo)
    valor = {h: max(0, niveles.get(h, 0)) for h in orden}

    # El tercer puesto decide si el segundo va clavado, así que hay que
    # conocerlo antes de resolver el segundo.
    tercero = valor[orden[2]] if len(orden) > 2 else 0
    cuarto = valor[orden[3]] if len(orden) > 3 else 0
    # El balon parado del portero NO abre la segunda: con Porteria 14, Defensa 6
    # y balon parado 9, la Defensa sigue clavada. Por eso se anula aqui.
    if len(orden) > 2 and orden[2] == BALON_PARADO:
        tercero = 0

    salida: list[Criterio] = []
    for puesto, habilidad in enumerate(orden):
        nivel = valor[habilidad]
        if habilidad == BALON_PARADO:
            salida.append(_balon_parado(nivel, holgado))
        elif puesto == 0:
            salida.append(Criterio(habilidad, "=", nivel, nivel))
        elif puesto == 1:
            salida.append(_segundo(habilidad, nivel, valor[orden[0]], tercero, cuarto, tipo))
        elif puesto == 2:
            salida.append(_tercero(habilidad, nivel, holgado))
        elif puesto == 3 and nivel >= ENTRADA_TERCERO:
            salida.append(_cuarto(habilidad, nivel, valor[orden[0]], tercero, holgado))
        else:
            salida.append(Criterio(habilidad, "<=", 0, _techo_de_sobrante(nivel, holgado)))

    minima, maxima = _ventana_de_edad(edad, holgado)
    return Criterios(
        edad_minima=minima,
        edad_maxima=maxima,
        habilidades=tuple(salida),
        holgado=holgado,
        tope_de_dias=(TOPE_DE_DIAS_OBSERVADO if edad == EDAD_CON_TOPE_DE_DIAS else None),
    )


def _segundo(
    habilidad: str, nivel: int, primero: int, tercero: int, cuarto: int, tipo: str
) -> Criterio:
    """El segundo puesto: techo si es bajísimo, clavado si es normal, banda si no.

    Lo de que el TERCERO abra al segundo no es un capricho: con Defensa 13 y
    Jugadas 9, Pases 6 deja Jugadas clavada y Pases 7 la abre. Lo decía ya el
    texto de 2009, sin dar el número.

    El empate con la primera también la abre: con (8,8,6) salió banda donde
    todo lo demás pedía clavada. Tiene sentido --si valen lo mismo, cuál es la
    segunda es dudoso-- pero es UN SOLO caso medido.

    El portero va por libre en los dos umbrales, y por eso entra el tipo aquí.
    """
    portero = tipo == "keeper"
    entrada = ENTRADA_SEGUNDO_PORTERO if portero else ENTRADA_SEGUNDO
    con_banda = SEGUNDO_CON_BANDA_PORTERO if portero else SEGUNDO_CON_BANDA
    if nivel < entrada:
        return Criterio(habilidad, "<=", 0, entrada - 1)
    # Y la CUARTA tambien la abre, si existe. El texto de 2009 lo decia:
    # «lo mismo ocurre si la tercera y la cuarta son bastante altas».
    abre = (
        nivel >= con_banda
        or tercero >= TERCERO_QUE_ABRE_AL_SEGUNDO
        or cuarto >= ENTRADA_TERCERO
        or nivel == primero
    )
    if not abre:
        return Criterio(habilidad, "=", nivel, nivel)
    return Criterio(habilidad, "banda", max(0, nivel - 1), nivel + 1)


def _cuarto(habilidad: str, nivel: int, primero: int, tercero: int, holgado: bool) -> Criterio:
    """El cuarto puesto, que sólo existe si llega al umbral de entrada.

    Barrido con Defensa 14, Jugadas 10 y Pases 8 de tercera, moviendo el
    Lateral de 5 a 11:

        Lat 5 -> 4-7    Lat 6 -> 5-8    Lat 7 -> 6-9     (estrecha, como la tercera)
        Lat 8 -> 6-11   Lat 9 -> 7-12                    (ancha)

    El salto está en OCHO, y no en alcanzar a la tercera: un cuarto puesto de 8
    recibe la banda ancha tanto con la tercera en 8 como con la tercera en 10.

    Y cuando empata con la PRIMERA --o sea, cuando las cuatro valen lo mismo--
    la banda se queda pegada por debajo: cuatro habilidades a 10 dan «Pas 9-12»
    de tercera y «Def 8-10» de cuarta; cuatro a 9 dan «Pas 8-10» y «Def 7-9».
    Con Defensa 16 y las otras tres a 8, en cambio, la cuarta recibe la banda
    ancha: lo que importa es empatar con la primera, no con la segunda.

    Las tres reglas reproducen las diez observaciones que hay. DESCONOCIDO qué
    hace un cuarto puesto de 8 o más con la búsqueda ajustada: todos los que se
    midieron ahí arriba cayeron del lado holgado.
    """
    if nivel == primero:
        return Criterio(habilidad, "banda", max(0, nivel - 2), nivel)
    if nivel >= CUARTO_CON_BANDA_ANCHA:
        return Criterio(habilidad, "banda", max(0, nivel - 2), nivel + 3)
    return _tercero(habilidad, nivel, holgado)


def _tercero(habilidad: str, nivel: int, holgado: bool) -> Criterio:
    """El tercer puesto: techo, banda o suelo según el nivel."""
    if nivel < ENTRADA_TERCERO:
        return Criterio(habilidad, "<=", 0, _techo_de_sobrante(nivel, holgado))
    if nivel >= SUELO_DEL_TERCERO:
        return Criterio(habilidad, ">=", nivel, MAXIMO_DE_LA_ESCALA)
    arriba = nivel + (2 if holgado else 1)
    return Criterio(habilidad, "banda", max(0, nivel - 1), arriba)
