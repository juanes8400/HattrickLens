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

#: Las seis habilidades, en el orden en que Hattrick decide DE QUÉ TIPO es el
#: jugador cuando dos valen lo mismo.
#:
#: Se midió por eliminación --las seis a 12, se mira cuál manda, se pone a cero
#: la ganadora y se repite-- y luego empate a empate, que es lo que vale: con
#: Lateral 10 y Portería 10 sale extremo, con Anotación 10 y Portería 10 sale
#: delantero, con Jugadas 10 y Portería 10 sale mediocentro, y con Defensa 12
#: y Jugadas 12 sale defensa.
#:
#: LA PRIMERA MEDIDA PUSO LA PORTERÍA TERCERA Y ERA FALSO. Salió de que con
#: todo a 12 gana el portero y de que con Portería 11 y Defensa 11 también.
#: Las dos cosas las explica el sesgo de `_umbral_de_portero`, no el desempate:
#: medido de uno en uno, la Portería pierde el empate contra Jugadas. Va
#: quinta, delante de Pases y detrás de todo lo demás.
ORDEN_LLANO: tuple[str, ...] = (
    "winger",
    "scoring",
    "defending",
    "playmaking",
    "keeper",
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


#: QUE HABILIDADES PUEDEN SER CRITERIO, por tipo. Las demas reciben tope
#: siempre, valgan lo que valgan. Medido levantando cada habilidad a 9 sobre
#: una dominante de 12 y mirando si sale como criterio o como tope:
#:
#:   portero    -> Defensa, Balon parado     (ni Jugadas, Lateral, Anotacion)
#:   defensa    -> Pases, Jugadas, Lateral    (ni Anotacion ni Porteria)
#:   jugadas    -> Defensa, Lateral, Pases, Anotacion  (nunca Porteria)
#:   lateral    -> Defensa, Jugadas, Pases, Anotacion  (nunca Porteria)
#:   anotacion  -> Jugadas, Lateral, Pases             (ni Porteria ni Defensa)
#:
#: Tiene sentido futbolistico: a un central no se le compara por Anotacion, a
#: un delantero no se le compara por Defensa, y a NADIE de campo por Porteria.
#: Lo del defensa se midio el 2026-10-12 barriendo su Porteria de 5 a 13 con
#: Defensa 18 --y de 5 a 7 con Defensa 12--: nunca llega a ser criterio, solo
#: le sube el techo. La primera medicion lo daba como elegible y era falso;
#: hacia que al defensa con algo de Porteria se le clavara como SEGUNDO
#: criterio, que es el error mas gordo que podia cometer aqui.
#: Es la lista de «secondary, tertiary and quartile skills» que el post de 2009
#: decia que se elegia por tipo de jugador, sin decir cual era.
#:
#: Explica el ultimo agujero que quedaba: tres jugadores reales con Anotacion 5
#: a los que Hattrick trataba distinto. No era el nivel, era el tipo.

#: EL ORDEN PARA DESEMPATAR NO ES EL MISMO QUE EL DE LA LISTA. En el extremo,
#: Anotacion pesa como si fuera el cuarto puesto --por delante de Defensa--
#: aunque en la lista de topes salga detras. Sale de una rejilla de 4x4 con
#: Lateral 10 y Pases 7 fijos, moviendo Jugadas y Anotacion de 5 a 8: los
#: dieciseis ordenes se reproducen con Anotacion en la posicion 3 y ninguno
#: con ella en la 4.
#:
#: Donde no se midio se usa la plantilla tal cual.
#: Se expresa como PESO por habilidad y no como lista, porque dos pueden pesar
#: lo mismo: en el extremo, Defensa y Anotacion comparten el tercer puesto y
#: entre ellas desempata el nivel. Eso reproduce a la vez la rejilla de 4x4
#: --donde Anotacion adelanta a Jugadas-- y un extremo real de Lateral 15,
#: Defensa 13 y Jugadas 11, donde Defensa adelanta a Jugadas.
#:
#: ESTE ORDEN ES UN AJUSTE, NO LA REGLA DE HATTRICK, y eso esta demostrado.
#: Ningun vector de pesos por habilidad puede reproducir lo medido el
#: 2026-10-11, porque lo medido no es un orden: depende del conjunto.
#:
#:   Extremo con Lateral 16 y todo lo demas a 9
#:     Pases, Anotacion            -> Pases, Anotacion
#:     Pases, Anotacion, Defensa   -> ANOTACION, Pases, Defensa
#:
#: Las mismas dos habilidades, los mismos niveles, y meter una tercera le da
#: la vuelta a su orden. Un `sorted` por clave no puede hacer eso, y tampoco
#: una lista por puesto ni una asignacion a huecos: las tres fallan la misma
#: pareja de casos. En el mediocentro pasa igual: con Jugadas 16, Pases 10 y
#: Anotacion 11 manda la Anotacion --haria falta que pesara 2-- pero con
#: Pases 7, Defensa 9 y Anotacion 8 manda Pases por delante de Anotacion
#: --haria falta que pesara 3--.
#:
#: Que queda en pie: el ajuste clava los 146 casos de la prueba, incluidas
#: las 24 fichas reales de la plantilla y la rejilla de 4x4. Falla en una
#: familia sintetica --tres habilidades secundarias juntas entre 7 y 9, con
#: alguna a cero-- que esta anotada entera en fase-a.txt, FASE Q. Mientras no
#: aparezca el mecanismo de verdad, esto es lo que hay, dicho como lo que es.
ORDEN_DE_IMPORTANCIA: dict[str, dict[str, int]] = {
    "winger": {
        "winger": 0,
        "playmaking": 1,
        "passing": 2,
        "defending": 3,
        "scoring": 3,
        "keeper": 5,
    },
    # EL MEDIOCENTRO TAMBIEN LE DA A LA ANOTACION EL PESO DE LA DEFENSA, y eso
    # estaba medido en FASE Q desde el 2026-10-11 y se habia quedado sin
    # escribir. Se destapo con Jugadas 16, Lateral 5 y Anotacion 5: Hattrick
    # lista «Anotacion = insuficiente» segunda y el Lateral tercero, y con la
    # Anotacion en el cuarto puesto de la plantilla salia al contrario.
    #
    # Las fronteras que lo fijan: con Pases 10, la Anotacion adelanta con 11 y
    # el Lateral necesita 12; con Lateral 7, la Anotacion empata y gana; con
    # Defensa 7, el Lateral necesita 8. Al reves que en el extremo, aqui el
    # empate entre Defensa y Anotacion lo gana la DEFENSA.
    "playmaking": {
        "playmaking": 0,
        "passing": 1,
        "defending": 2,
        "scoring": 2,
        "winger": 3,
        "keeper": 5,
    },
}

EXCLUIDAS: dict[str, frozenset[str]] = {
    "keeper": frozenset({"playmaking", "winger", "scoring"}),
    "defending": frozenset({"scoring", "keeper"}),
    "playmaking": frozenset({"keeper"}),
    "winger": frozenset({"keeper"}),
    "passing": frozenset({"keeper"}),
    "scoring": frozenset({"keeper", "defending"}),
}

#: Y UNA EXCLUSION QUE DEPENDE DEL NIVEL. Al extremo, la Defensa no le es
#: criterio si no llega al nivel de la Anotacion. Medido el 2026-10-12 con
#: Lateral 16 y 18:
#:
#:   Lat18 Ano12 Def 7..11  ->  la Defensa solo sube de techo, no entra
#:   Lat18 Ano12 Def 12     ->  entra, y la Anotacion le cede el segundo puesto
#:   Lat18 Ano9  Def 5..8   ->  no entra
#:   Lat18 Ano9  Def 9      ->  entra
#:
#: Y NO es simetrico: con la Defensa arriba, la Anotacion entra siempre.
#:
#:   Lat18 Def12 Ano 9, 10, 11, 12  ->  la Anotacion entra en los cuatro
#:
#: Tampoco es general: al mediocentro --donde la Anotacion tambien comparte
#: peso con la Defensa-- no le pasa; con Jugadas 18 y Anotacion 12, una Defensa
#: 9 es criterio. Ni al defensa con su Lateral. Es del extremo y de esa pareja.
#:
#: Esto explica cuatro de los seis contraejemplos de FASE Q que se quedaron sin
#: explicar: con Lateral 16, «Pases 9 Anotacion 8 Defensa 7» no saca criterio
#: de la Defensa y «Pases 9 Anotacion 7 Defensa 8» si.
DEFENSA_DEL_EXTREMO_PIDE_LA_ANOTACION = True


#: EL LATERAL DEL MEDIOCENTRO PIDE MAS QUE LOS DEMAS. Entra como criterio con
#: 7, o con 5 si la Anotacion llega a 5 y la Defensa no pasa de 4. Medido el
#: 2026-10-12 en unas noventa celdas:
#:
#:   Jug 12,14,16,18,20 + Pas9, Lateral de 4 a 9  -> cinco filas iguales, 7
#:   Jug16 + Def10,      Lateral de 4 a 8         -> 7
#:   Jug16 + Ano10,      Lateral de 4 a 8         -> 5
#:   Jug16 Lat5 Def0,  Anotacion de 4 a 9         -> entra desde Ano 5
#:   Jug16 Lat5 Ano10, Defensa   de 4 a 9         -> deja de entrar en Def 5
#:   Jug16 Lat5 Ano14, Defensa   de 4 a 9         -> igual
#:
#: El 5 de la Anotacion y el 4 de la Defensa son justo las fronteras de SER
#: CRITERIO: el Lateral del mediocentro entra barato cuando la Anotacion es
#: criterio y la Defensa no. Es la lectura de mediocentro OFENSIVO, y por eso
#: se escribe, pero sigue siendo una regla local, no el mecanismo: el porque
#: esta en la hipotesis de los PUESTOS, en CRITERIOS_DEL_COMPARADOR.md.
LATERAL_DEL_MEDIO_SIN_AYUDA = 7


def _fuera(tipo: str, niveles: dict[str, int]) -> frozenset[str]:
    """Las habilidades que no pueden ser criterio para este jugador."""
    fuera = EXCLUIDAS[tipo]
    # LA ANOTACION NECESITA CINCO; A LAS DEMAS LES BASTA TRES. Medido el
    # 2026-10-12 poniendo una sola companera a la dominante:
    #
    #   Lat16 Ano3 / Ano4 -> tope ; Ano5 -> «Anotacion = insuficiente»
    #   Jug16 Ano4        -> tope ; Ano5 -> criterio
    #   Lat16 Def3, Def4, Jug3, Jug4, Pas3, Pas4 -> criterio los seis
    #   Ano16 Lat4, Jug4 ; Def16 Pas4, Jug4      -> criterio los cuatro
    #
    # Es de la habilidad, no del tipo: pasa igual en el extremo y en el
    # mediocentro, y es lo mismo que ya pedia de tercera.
    if niveles.get("scoring", 0) < ENTRADA_TERCERO:
        fuera |= {"scoring"}
    # Y LA TAPADERA SOLO MUERDE SI LA ANOTACION ES CRITERIO. Con Lateral 16,
    # Defensa 3 y Anotacion 4, la Defensa 3 SI es criterio: una Anotacion que
    # no llega a 5 no tapa a nadie. Medido tambien con Ano2, Def4 y Def6.
    if (
        tipo == "winger"
        and "scoring" not in fuera
        and niveles.get("defending", 0) < niveles.get("scoring", 0)
    ):
        fuera |= {"defending"}
    if tipo == "playmaking" and niveles.get("winger", 0) < LATERAL_DEL_MEDIO_SIN_AYUDA:
        ofensivo = (
            niveles.get("scoring", 0) >= ENTRADA_TERCERO
            and niveles.get("defending", 0) < ENTRADA_TERCERO
        )
        if not ofensivo:
            fuera |= {"winger"}
    return fuera


#: CUANDO DOS PESAN LO MISMO, QUIEN VA DELANTE. Solo hace falta donde dos
#: habilidades comparten peso, y eso hoy solo pasa en el extremo, entre la
#: Defensa y la Anotacion. Lo gana la Anotacion, y esta medido cuatro veces
#: --con las dos a 6, a 8, a 10 y a 13 sobre un Lateral 16-- mas un quinto
#: caso de perfil realista: Lateral 15, Jugadas 12, Defensa 11, Anotacion 11,
#: que lista la Anotacion tercera y la Defensa cuarta.
#:
#: Ojo: en el mediocentro, donde la Anotacion tambien pesa como la Defensa, el
#: empate lo gana la DEFENSA. Por eso esto va por tipo y no es una regla sola.
DESEMPATE: dict[str, tuple[str, ...]] = {
    "winger": ("winger", "playmaking", "passing", "scoring", "defending", "keeper"),
}

#: Por debajo de esto, una habilidad no es criterio de identidad: cae al montón
#: de los techos. El segundo puesto entra antes que el tercero, y el portero
#: antes que nadie: a su Defensa le basta un 2 donde al resto le hacen falta 3.
#: El techo que le ponen mientras no entra es siempre la entrada menos uno.
#:
#: DESCONOCIDO: EL UMBRAL DEL TERCERO NO ES ABSOLUTO. Medido el 2026-10-12: con
#: Lateral 16 y Anotación 14, una Defensa de 3 a 8 nunca llega a ser criterio
#: --sólo le sube el techo-- y con Lateral 12 y Anotación 8 la Defensa entra
#: justo al empatar con la segunda, en 8. Pero con Lateral 10 y Pases 7 la
#: Jugadas 5 sí entra, dos niveles por debajo de la segunda. Depende de lo que
#: tenga por encima, y la regla no se ha sacado. El 5 de aquí es el ajuste que
#: mejor encaja: le cuesta 1 de 60 en los tres filtros de `transfersearch` y 4
#: de 60 en la cadena entera. Las medidas están en fase-a.txt, FASE R.
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
#: LA CUARTA NO ABRE AL SEGUNDO: eso fue una lectura mal hecha. El 2026-10-12
#: se barrio el eje entero --Lateral 10, Pases 7, Jugadas 5 y la Anotacion de
#: 4 a 8-- y la segunda sigue clavada con la cuarta en 4, 5 y 6. Lo que la
#: abre en 7 es que la Anotacion adelanta a Jugadas y pasa a ser TERCERA, que
#: es la regla de arriba. Confirmado por segunda via con Lateral 8, Pases 7,
#: Jugadas 6 y la Defensa de 4 a 7: clavada en los cuatro.
#:
#: El umbral se queda, pero solo para el dial: un CUARTO criterio de identidad
#: baja el liston de la rareza un punto, y eso si esta medido aparte.
CUARTA_QUE_BAJA_EL_LISTON = 6
#: Y un cuarto criterio de identidad baja el umbral del dial DOS puntos. Sale
#: de la rejilla fina de la tercera contra la cuarta: con Defensa 12 y Pases 10
#: fijos, (Jug 6, Lat 6) sale ajustado y (Jug 6, Lat 7) holgado, y entre los
#: dos solo hay un punto de rareza.
REBAJA_POR_CUARTO_CRITERIO = 2

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
#: Y de aquí en adelante, si la búsqueda va ajustada, la edad deja de ser una
#: ventana y pasa a ser un SUELO abierto: «Edad >= 35», sin tope por arriba.
#: Medido con un perfil ajustado: 32→31-33, 33→32-34, 34→33-35 y 35, 36 y 40
#: todos a «>= 35». Con un perfil holgado no pasa: 35→34-36 y 36→35-37.
#:
#: No se habia visto antes porque el sondeo se acoto a 17-33 anos por decision
#: del usuario. Salio al validar contra su plantilla real, donde hay fichas de
#: 41 y 43 anos.
EDAD_DEL_SUELO_ABIERTO = 35
#: A los 17, y sólo a los 17, Hattrick añade un tope de días. El número es
#: FIJO, no sale del jugador: se pidió el mismo perfil de 17 años desde la
#: ficha de uno de 2 días y desde la de uno de 20, y las dos veces salió 24.
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

#: Lo que llega el desplegable de edad del panel. Se usa como tope del suelo
#: abierto de los mayores, que no tiene maximo de verdad.
EDAD_MAXIMA_DE_LA_ESCALA = 99


#: EL SUELO Y EL SESGO DEL PORTERO. La Portería no compite de igual a igual con
#: la Defensa: le gana desde cuatro niveles más abajo. Se bisectó la frontera
#: para cada Defensa de 1 a 20 --el resto del perfil a cero-- y salió la tabla
#: entera, que es exactamente `max(4, d - 3)` hasta Defensa 11 y `d - 4` desde
#: Defensa 12:
#:
#:   Defensa   1  2  3   4  5  6  7   8  9 10 11  12 13 14 15 16 17 18 19 20
#:   Portería  -  -  -   4  4  4  4   5  6  7  8   8  9 10 11 12 13 14 15 16
#:
#: Es lo único que rompe «manda la habilidad más alta»: se comprobaron las
#: treinta parejas con una a 16 y otra a 13 y ninguna otra se sale.
#:
#: No influye nada más: con Defensa 16 la frontera sigue en 12 con Pases 0 o
#: 10, con Lateral 14, con Jugadas 15, con Anotación 15 y con balón parado 20.
#: Y sí se aplica contra una Defensa que ganó por reclasificación: con Pases
#: 16 y Defensa 14 la frontera es 10, la de la Defensa.
#:
#: POR QUÉ EL ESCALÓN EN 12 NO SE SABE. Sale medido, no deducido; la tabla es
#: el dato y la fórmula sólo la escribe corto. Fuera de 1 a 20 no se sondeó.
SUELO_DEL_PORTERO = 4
VENTAJA_DEL_PORTERO = 3
DEFENSA_QUE_DA_UN_NIVEL_MAS = 12


def _umbral_de_portero(defensa: int) -> int:
    """Cuánta Portería hace falta para que gane a esa Defensa."""
    ventaja = VENTAJA_DEL_PORTERO + (1 if defensa >= DEFENSA_QUE_DA_UN_NIVEL_MAS else 0)
    return max(SUELO_DEL_PORTERO, defensa - ventaja)


def _tipo(niveles: dict[str, int]) -> str:
    """La habilidad dominante, que es la que elige la plantilla.

    PRIMERO SE DECIDE EL REY DE CAMPO, sin contar la Portería, porque la
    Portería no juega en esa liga: pelea aparte.

    CON UNA EXCEPCIÓN: Hattrick no tiene puesto de pasador. Cuando lo que más
    tiene el jugador son Pases, el tipo lo decide la MEJOR DE LAS DEMÁS --un
    Pases 15 con Jugadas 12 y Lateral 9 se trata como mediocentro, y sus
    criterios empiezan por «Jugadas = magnífico»--. Si no tiene ninguna otra,
    cae en extremo, que es el primero del desempate.

    DESPUÉS ENTRA LA PORTERÍA. Contra la Defensa, con el sesgo medido en
    `_umbral_de_portero`: Defensa 16 y Portería 12 es un portero. Contra todo
    lo demás tiene que ganar de verdad, y el empate lo pierde: con Jugadas 10
    y Portería 10 sale mediocentro.
    """
    campo = [h for h in ORDEN_LLANO if h != "keeper"]
    rey = min(campo, key=lambda h: (-niveles.get(h, 0), campo.index(h)))
    if rey == "passing":
        resto = [h for h in campo if h != "passing"]
        rey = min(resto, key=lambda h: (-niveles.get(h, 0), resto.index(h)))

    porteria = niveles.get("keeper", 0)
    if rey == "defending":
        if porteria >= _umbral_de_portero(niveles.get("defending", 0)):
            return "keeper"
        return rey
    if porteria > niveles.get(rey, 0):
        return "keeper"
    return rey


def rareza(niveles: dict[str, int], tipo: str | None = None) -> int:
    """La medida que mueve el dial.

    La primera y la segunda cuentan enteras; de la tercera en adelante sólo lo
    que pasa de seis, y sólo cuentan cuatro habilidades. Es la fórmula que
    reproduce las parejas frontera medidas: (16,9) afloja y (16,8) no; (13,12)
    afloja y (12,12) no; (14,10,7) afloja y (14,10,6) no.
    """
    tipo = tipo or _tipo(niveles)
    # LO QUE NO PUEDE SER CRITERIO TAMPOCO CUENTA PARA LA RAREZA. Medido con un
    # defensa de Defensa 12, Pases 10 y Anotacion 9: sigue saliendo ajustado,
    # cuando contando la Anotacion se pasaria de 25. A Hattrick, un central
    # golead­or no le parece un jugador mas raro: le parece el mismo central.
    plantilla = [h for h in PLANTILLAS[tipo] if h not in EXCLUIDAS[tipo]]
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


#: EL LISTON NO ES POR TIPO: ES POR PAREJA. Se media con una sola segunda
#: habilidad por tipo y de ahi salio `UMBRAL_POR_TIPO`. El 2026-10-12 se
#: barrieron doce parejas con la primera en 16 y sale que depende de las DOS:
#:
#:   defensa     + Pases 9, Jugadas 9, Lateral 9     -> afloja en rareza 25
#:   mediocentro + Pases 11                          -> 27
#:   mediocentro + Defensa 10                        -> 26
#:   mediocentro + Lateral 9, Anotacion 9            -> 25
#:   extremo     + Pases 11                          -> 27
#:   delantero   + Pases 11, Jugadas 11              -> 27
#:   delantero   + Lateral 9                         -> 25
#:   portero     + Defensa 5                         -> 21
#:
#: Se lee como una prima de raridad de la pareja: las parejas naturales --el
#: mediocentro que pasa, el extremo que pasa, el delantero que pasa-- piden 27,
#: y las raras aflojan antes. POR QUE no se sabe, y con doce celdas no se
#: inventa la tabla entera: lo que no esta medido cae en `UMBRAL_POR_TIPO`.
UMBRAL_POR_PAREJA: dict[tuple[str, str], int] = {
    ("defending", "passing"): 25,
    ("defending", "playmaking"): 25,
    ("defending", "winger"): 25,
    ("playmaking", "passing"): 27,
    ("playmaking", "defending"): 26,
    ("playmaking", "winger"): 25,
    ("playmaking", "scoring"): 25,
    ("winger", "passing"): 27,
    ("scoring", "passing"): 27,
    ("scoring", "playmaking"): 27,
    ("scoring", "winger"): 25,
    ("keeper", "defending"): 21,
}


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
    # AQUI TAMBIEN CUENTAN SOLO LAS ELEGIBLES, igual que en `rareza`. Era un
    # agujero: a un mediocentro de Jugadas 14 y Porteria 13 le contaba la
    # Porteria como segunda y lo aflojaba --empate arriba y liston a 25--
    # cuando Hattrick le clava la edad. Medido con Jugadas 14, Porteria 13,
    # Lateral 9, Pases 8 y Defensa 5 a los 29 anos: sale ajustado.
    elegibles = [h for h in PLANTILLAS[tipo] if h not in _fuera(tipo, niveles)]
    v = sorted((max(0, niveles.get(h, 0)) for h in elegibles), reverse=True)
    orden = _puestos(niveles, tipo)
    segunda = orden[1] if len(orden) > 1 else ""
    umbral = UMBRAL_POR_PAREJA.get((tipo, segunda), UMBRAL_POR_TIPO[tipo])
    # Un CUARTO criterio de identidad baja el liston un punto: un jugador con
    # cuatro habilidades de verdad encaja en menos moldes que uno con tres.
    # Medido con un delantero de Anotacion 11, Pases 10, Lateral 9 y Jugadas 8
    # --rareza 26-- que afloja, cuando el mismo tipo con solo dos habilidades
    # aguantaba hasta 27.
    if len(v) > 3 and v[3] >= CUARTA_QUE_BAJA_EL_LISTON:
        umbral -= REBAJA_POR_CUARTO_CRITERIO
    if len(v) > 1 and v[0] == v[1]:
        umbral = min(umbral, UMBRAL_CON_EMPATE_ARRIBA)
    return rareza(niveles, tipo) >= umbral or v[0] >= PRIMERA_QUE_AFLOJA_SOLA


def _ventana_de_edad(edad: int, holgado: bool, pasador: bool = False) -> tuple[int, int]:
    """La ventana de edad.

    EL PASADOR VA POR LIBRE, otra vez. A quien lo más alto que tiene son Pases
    la edad NO se le abre a los 32: le aguanta clavada hasta los 34. Medido
    contra su gemelo: con Pases 13 y Jugadas 7 sale «= 32», «= 33» y «= 34»,
    y dándole la vuelta --Jugadas 13 y Pases 7-- sale «31-33», «32-34» y
    «33-35». Es la misma excepción que le fuerza el primer criterio, asomando
    por otro sitio.
    """
    if edad <= EDAD_QUE_APRIETA_TODO:
        return edad, edad
    if not holgado and edad >= EDAD_DEL_SUELO_ABIERTO:
        return EDAD_DEL_SUELO_ABIERTO, EDAD_MAXIMA_DE_LA_ESCALA
    if (edad >= EDAD_SIEMPRE_ABIERTA and not pasador) or holgado:
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
        # NO REORDENA, PERO SI EXCLUYE. Era un agujero: al portero se le
        # colaba un cuarto criterio de Lateral --Porteria 18, Defensa 15 y
        # Lateral 5 sacaba «Lateral entre debil y bueno»-- cuando Hattrick le
        # pone tope. Sus Jugadas, Lateral y Anotacion nunca son criterio.
        fuera_del_portero = _fuera(tipo, niveles)
        dentro = [h for h in plantilla if h not in fuera_del_portero]
        return dentro + [h for h in plantilla if h in fuera_del_portero]

    pesos = ORDEN_DE_IMPORTANCIA.get(tipo) or {h: i for i, h in enumerate(plantilla)}
    desempate = DESEMPATE.get(tipo) or plantilla

    def clave(h: str) -> tuple[int, int, int]:
        # ADELANTAR CUESTA. Una habilidad sólo pasa por delante de otra si le
        # saca tantos niveles como puestos las separan en la plantilla. Es un
        # ajuste que clava todo lo medido salvo la familia de FASE Q; el
        # comentario de `ORDEN_DE_IMPORTANCIA` dice por qué no es la regla.
        # Medido:
        # con Pases 7, Jugadas --que va justo detrás-- adelanta con 8, pero
        # Lateral --dos puestos más atrás-- necesita 9. Con Pases 10, Lateral
        # necesita 12. Con Pases 3, Lateral necesita 5. Siempre la distancia.
        #
        # Es la regla que flameron describió en 2009 sin dar el número, y la
        # que a mí se me escapó: barriendo un eje cada vez nunca aparece.
        pos = pesos[h]
        return (-(niveles.get(h, 0) - pos), -niveles.get(h, 0), desempate.index(h))

    def clave_de_corte(h: str) -> tuple[int, int, int]:
        # ELEGIR Y LISTAR NO DESEMPATAN IGUAL. Cuando la Defensa y la Anotacion
        # empatan y solo cabe una, Hattrick se queda con la DEFENSA; cuando
        # caben las dos, lista la ANOTACION delante. Medido tres veces de cada:
        #
        #   Lat13 Pas15 Jug13 Ano13 Def13 -> Lat, Pas, Jug, DEFENSA (Ano al tope)
        #   Lat7  Jug6  Pas6  Ano6  Def6  -> Lat, Jug, Pas, DEFENSA (Ano al tope)
        #   Lat18 Def12 Ano12             -> Lat, ANOTACION, Defensa (las dos)
        #
        # Asi que el corte usa el orden de la plantilla y la lista el desempate.
        pos = pesos[h]
        return (-(niveles.get(h, 0) - pos), -niveles.get(h, 0), plantilla.index(h))

    fuera = _fuera(tipo, niveles)
    ordenadas = [h for h in sorted(plantilla, key=clave_de_corte) if h not in fuera]
    cuantos = PUESTOS_DE_IDENTIDAD
    if len(ordenadas) > cuantos and niveles.get(ordenadas[cuantos], 0) >= ENTRADA_TERCERO:
        cuantos += 1
    cabeza = sorted(ordenadas[:cuantos], key=clave)
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
    fuera = _fuera(tipo, niveles)
    orden = _puestos(niveles, tipo)
    valor = {h: max(0, niveles.get(h, 0)) for h in orden}

    # El tercer puesto decide si el segundo va clavado, así que hay que
    # conocerlo antes de resolver el segundo.
    tercero = valor[orden[2]] if len(orden) > 2 else 0
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
            salida.append(_segundo(habilidad, nivel, valor[orden[0]], tercero, tipo))
        elif puesto == 2:
            salida.append(_tercero(habilidad, nivel, holgado))
        # LO EXCLUIDO NO PUEDE SER EL CUARTO. Era un agujero del portero: con
        # Porteria 18, Defensa 15 y Lateral 5 le salia «Lateral entre debil y
        # bueno» cuando Hattrick le pone tope, y de rebote el Lateral abria la
        # banda de la Defensa.
        elif puesto == 3 and nivel >= ENTRADA_TERCERO and habilidad not in fuera:
            salida.append(_cuarto(habilidad, nivel, valor[orden[0]], tercero, holgado))
        else:
            salida.append(Criterio(habilidad, "<=", 0, _techo_de_sobrante(nivel, holgado)))

    domina = min(ORDEN_LLANO, key=lambda h: (-max(0, niveles.get(h, 0)), ORDEN_LLANO.index(h)))
    minima, maxima = _ventana_de_edad(edad, holgado, pasador=domina == "passing")
    return Criterios(
        edad_minima=minima,
        edad_maxima=maxima,
        habilidades=tuple(salida),
        holgado=holgado,
        tope_de_dias=(TOPE_DE_DIAS_OBSERVADO if edad == EDAD_CON_TOPE_DE_DIAS else None),
    )


def _segundo(habilidad: str, nivel: int, primero: int, tercero: int, tipo: str) -> Criterio:
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
    abre = nivel >= con_banda or tercero >= TERCERO_QUE_ABRE_AL_SEGUNDO or nivel == primero
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

    Y LA BANDA SE CORTA EN LA PRIMERA HABILIDAD, que es lo que ata todo el
    rincón. Con Defensa 9 y las otras tres a 8 sale «Lat 6-9»; subiendo sólo la
    Defensa a 10 sale «Lat 6-10». El techo no es del cuarto puesto: es el nivel
    del jugador. Tiene sentido --un cuarto puesto no puede ser mejor que lo
    mejor que tiene-- y de paso explica los perfiles planos, que parecían un
    caso aparte: cuatro habilidades a 10 dan «Def 8-10» y cuatro a 9 dan
    «Def 7-9» simplemente porque ahí el corte cae encima.
    """
    if nivel >= CUARTO_CON_BANDA_ANCHA:
        return Criterio(habilidad, "banda", max(0, nivel - 2), min(nivel + 3, primero))
    return _tercero(habilidad, nivel, holgado)


def _tercero(habilidad: str, nivel: int, holgado: bool) -> Criterio:
    """El tercer puesto: techo, banda o suelo según el nivel."""
    if nivel < ENTRADA_TERCERO:
        return Criterio(habilidad, "<=", 0, _techo_de_sobrante(nivel, holgado))
    if nivel >= SUELO_DEL_TERCERO:
        return Criterio(habilidad, ">=", nivel, MAXIMO_DE_LA_ESCALA)
    arriba = nivel + (2 if holgado else 1)
    return Criterio(habilidad, "banda", max(0, nivel - 1), arriba)
