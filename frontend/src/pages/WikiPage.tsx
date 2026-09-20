import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { tx } from "../i18n/tx";
/**
 * Wiki (2026-09-14, pedido del usuario): la documentación de todo HT Lens,
 * escrita desde la pantalla. Qué responde cada módulo, cómo se calcula, cómo
 * se lee, qué decisión ayuda a tomar y hasta dónde vale.
 *
 * Segunda versión, el mismo día: el usuario pidió subir la profundidad de las
 * explicaciones «de 2 a 7,2». Cada artículo pasa de una descripción a un
 * capítulo con fórmulas, constantes, ejemplos y límites, sacados del mismo
 * catálogo de cálculos que publica Transparencia.
 *
 * El contenido es dato (una lista de artículos) para que buscar sea filtrar y
 * para que añadir un módulo sea añadir un objeto.
 */

type Seccion = {
  titulo: string;
  texto?: string[];
  /** Una lista de puntos, para enumeraciones que en prosa se pierden. */
  puntos?: string[];
  /** Una fórmula o una cuenta, en letra de ancho fijo. */
  formula?: string;
};

type Articulo = {
  id: string;
  grupo: string;
  titulo: string;
  /** La pantalla que documenta, si tiene una. */
  ruta?: string;
  resumen: string;
  secciones: Seccion[];
};

const ARTICULOS: Articulo[] = [
  // ── Empezar ──────────────────────────────────────────────────────────────
  {
    id: "que-es",
    grupo: tx("Empezar"),
    titulo: tx("Qué es HT Lens"),
    resumen: tx(
      "Una herramienta de análisis para managers de Hattrick: lee los datos de tu club y los convierte en respuestas con su porqué.",
    ),
    secciones: [
      {
        titulo: tx("Para qué sirve"),
        texto: [
          tx(
            "Hattrick enseña muchos números pero pocas conclusiones. HT Lens hace el paso que falta: cruza la plantilla, los partidos, la economía, la liga y la academia para contestar preguntas de gestión. Cada pantalla tiene una pregunta concreta escrita bajo su título, y todo lo que hay en ella existe para responderla.",
          ),
          tx(
            "No juega por ti ni toma decisiones: te da la información ordenada y con su margen de error para que decidas mejor. Cuando un número es una estimación lo dice, y cuando algo no se puede saber lo dice también en vez de rellenarlo.",
          ),
        ],
      },
      {
        titulo: tx("Tres principios que se repiten en toda la app"),
        puntos: [
          tx(
            "Lo medido y lo estimado no se mezclan sin decirlo. Un sueldo estimado, una proyección de caja o un pronóstico van marcados como tales.",
          ),
          tx(
            "Un hueco se queda en hueco. Si un dato no existe, la pantalla enseña «-», nunca un cero que se leería como un valor real.",
          ),
          tx(
            "Cada cálculo es comprobable. Las fórmulas, sus constantes y sus límites están en Transparencia, y esta Wiki las explica en lenguaje llano.",
          ),
        ],
      },
      {
        titulo: tx("De dónde salen los datos"),
        texto: [
          tx(
            "De tu propio club en Hattrick, a través de la conexión oficial que autorizas al entrar. HT Lens nunca ve tu contraseña. Los datos se guardan al sincronizar, así que las pantallas cargan rápido y conservan la historia aunque Hattrick sólo publique las últimas semanas. La excepción son los rivales: de ellos sólo se lee lo público, en vivo, cada vez que abres su ficha.",
          ),
        ],
      },
      {
        titulo: tx("Cómo está organizado el menú"),
        puntos: [
          tx(
            "Club: el equipo y su gente (Dashboard, Club y cuerpo técnico, Habilidades, Jugadores, Equipo, Posiciones y Alineación).",
          ),
          tx(
            "Desarrollo: cómo crece la plantilla (Entrenamiento, Juveniles y Transferencias).",
          ),
          tx(
            "Competición: lo que pasa en el campo (Partidos, Liga, Copa y Rivales).",
          ),
          tx("Negocio: el dinero (Economía y Estadio)."),
          tx(
            "Inteligencia: la app sobre sí misma (Sincronización, Cambios, Alertas, Transparencia y esta Wiki).",
          ),
          tx("Acerca de: Autor, Libro de visitas y Apoyar el proyecto."),
        ],
      },
    ],
  },
  {
    id: "conectar",
    grupo: tx("Empezar"),
    titulo: tx("Conectar y sincronizar"),
    ruta: "/sync",
    resumen: tx(
      "La primera vez se trae la historia completa del club; después sólo lo nuevo, sin volver a pedir lo que ya está guardado.",
    ),
    secciones: [
      {
        titulo: tx("Conectar tu club"),
        texto: [
          tx(
            "En la bienvenida pulsas «Conecta tu club». Hattrick te pide autorizar a HT Lens con su propia pantalla de permisos; al aceptar vuelves a la app, eliges el equipo (si manejas más de uno) y empieza la primera importación. Si Hattrick no devuelve ningún club administrado, la app lo dice y te deja repetir la conexión.",
          ),
          tx(
            "Si más adelante la sesión con Hattrick vence, las pantallas lo avisan con un botón para reconectar. Los datos ya importados no se pierden.",
          ),
        ],
      },
      {
        titulo: tx("La primera sincronización"),
        texto: [
          tx(
            "Es la más larga porque trae todo lo que se puede recuperar hacia atrás:",
          ),
        ],
        puntos: [
          tx(
            "Plantilla completa con habilidades, forma, resistencia, experiencia, fidelidad, TSI, salario, especialidad y carácter.",
          ),
          tx("Cuerpo técnico, espíritu, confianza, socios y afición."),
          tx("Economía de la semana en curso y de la última semana cerrada."),
          tx("Estadio: aforo por sector y asistencia de los partidos en casa."),
          tx(
            "Academia: canteranos, lo revelado por los ojeadores y el informe inicial de cada uno, que se guarda una sola vez.",
          ),
          tx("Liga, calendario y copa."),
          tx(
            "La historia completa de partidos del equipo, pedida por tramos de 12 semanas, y el detalle de todos ellos de una vez.",
          ),
          tx("El libro de transferencias con compras y ventas."),
        ],
      },
      {
        titulo: tx("Las siguientes sincronizaciones"),
        texto: [
          tx(
            "Desde la pantalla Sincronización se traen sólo los datos nuevos. Lo que ya está guardado (un partido jugado, una transferencia cerrada) no se vuelve a pedir, así que cada sincronización es corta. Las lecturas de plantilla se acumulan semana a semana: de ahí salen las gráficas de evolución, las subidas confirmadas y la detección de cambios.",
          ),
          tx(
            "La barra superior dice cuánto hace de la última sincronización («Datos de hace 1 h»). Si pasa más de un día, Alertas lo avisa. Al terminar, Cambios resume lo que se movió.",
          ),
        ],
      },
      {
        titulo: tx("Por qué conviene sincronizar a menudo"),
        texto: [
          tx(
            "Hattrick sólo sirve algunas cosas durante un tiempo corto: la economía detallada de las dos últimas semanas, el calendario de un mes o el estado de la plantilla de hoy. Lo que no se guarda a tiempo no se puede reconstruir después. Sincronizar una vez por semana, después del partido y del entrenamiento, deja la historia completa.",
          ),
        ],
      },
    ],
  },
  {
    id: "leer",
    grupo: tx("Empezar"),
    titulo: tx("Cómo leer las pantallas"),
    resumen: tx(
      "Colores, signos de ayuda, tablas, pestañas y enlaces que se repiten en toda la app.",
    ),
    secciones: [
      {
        titulo: tx("La pregunta de cada pantalla"),
        texto: [
          tx(
            "Bajo cada título hay una frase corta: es la pregunta que responde esa pantalla. Si lo que buscas no encaja con esa frase, probablemente está en otro módulo; esta Wiki y su buscador ayudan a encontrarlo.",
          ),
        ],
      },
      {
        titulo: tx("Indicadores y los «?»"),
        texto: [
          tx(
            "Arriba de casi todas las pantallas hay una fila de indicadores: una cifra grande, una etiqueta y una pista debajo. El «?» junto a la etiqueta explica al pasar el cursor qué es exactamente ese número y de dónde sale. Un indicador en rojo pide atención; en verde, es una buena noticia.",
          ),
        ],
      },
      {
        titulo: tx("Colores y estados"),
        puntos: [
          tx("Verde: bueno, cubierto o por encima de lo esperado."),
          tx("Ámbar: cuidado, algo que vigilar."),
          tx("Rojo: un problema o un peligro."),
          tx("Azul: el color de acento, para selecciones y enlaces."),
          tx(
            "En Equipo los estados llevan íconos: ✅ Cubierto, ⚠️ Cuidado y 🚨 Hueco.",
          ),
        ],
      },
      {
        titulo: tx("Tablas"),
        texto: [
          tx(
            "Las tablas se ordenan pulsando la cabecera (una vez ascendente, otra descendente). Algunas columnas ordenan por un valor distinto del que muestran: «Mejor TSI (jugador)» enseña el nombre pero ordena por TSI. Un «-» en una celda significa que ese dato no existe o no aplica.",
          ),
        ],
      },
      {
        titulo: tx("Filtros y selectores"),
        texto: [
          tx(
            "Los filtros van arriba del contenido que filtran: temporada, oficiales o amistosos, formación, método de resumen. Cambiarlos no borra la pantalla: se sigue viendo el resultado anterior hasta que llega el nuevo.",
          ),
        ],
      },
      {
        titulo: tx("Transparencia"),
        texto: [
          tx(
            "Las pantallas con cálculos llevan un enlace a Transparencia, donde está la fórmula exacta con sus constantes, las fuentes, un ejemplo paso a paso y los límites. Si una cifra te sorprende, ése es el lugar para comprobarla.",
          ),
        ],
      },
    ],
  },

  // ── Club ─────────────────────────────────────────────────────────────────
  {
    id: "dashboard",
    grupo: tx("Club"),
    titulo: tx("Dashboard"),
    ruta: "/dashboard",
    resumen: tx(
      "La foto del club para decidir en un minuto: lo que viene, lo que pide atención y el estado general.",
    ),
    secciones: [
      {
        titulo: tx("Qué pregunta responde"),
        texto: [
          tx(
            "«¿Qué tengo que mirar hoy?». Está pensado para abrirlo después de sincronizar: arriba lo que viene (partido, liga, copa), en medio las alertas y debajo el estado del club.",
          ),
        ],
      },
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Próximo partido: rival, fecha, competición y el pronóstico con victoria, empate y derrota.",
          ),
          tx(
            "Liga resumida: puesto, puntos y la probabilidad de cada final de temporada.",
          ),
          tx(
            "Copa resumida: si sigues en competencia y qué te juegas en el próximo cruce.",
          ),
          tx(
            "Forma del equipo: los últimos resultados en barras, fáciles de leer de un vistazo.",
          ),
          tx(
            "Moral y confianza: el espíritu del equipo y la confianza, con su nivel en palabras.",
          ),
          tx(
            "Caja proyectada: el saldo semana a semana sin compraventa (ver Economía).",
          ),
          tx(
            "Subidas recientes: qué habilidades subieron en las últimas semanas y a quién.",
          ),
          tx("Alertas que requieren tu atención, con opción de archivarlas."),
          tx(
            "Mejor once, con el selector de formación, Defensas Centrales y Mediocentros.",
          ),
          tx("La flor de fuerza frente a la serie."),
        ],
      },
      {
        titulo: tx("La flor de fuerza"),
        texto: [
          tx(
            "Compara a tu equipo con los otros siete de la serie en ocho pétalos. Cada pétalo se normaliza entre el peor y el mejor de la serie, así que 0 es el peor, 1 el mejor y el tamaño del pétalo dice dónde estás tú.",
          ),
        ],
        puntos: [
          tx(
            "Ataque, Defensa y Mediocampo: la media de HatStats de cada sector en los últimos 5 partidos oficiales de cada equipo.",
          ),
          tx("TSI: el valor de las plantillas."),
          tx("Forma, Experiencia y Resistencia: las medias de cada plantilla."),
          tx("Posición: el puesto esperado en la proyección de liga."),
        ],
        formula: tx(
          "pétalo = (tu valor − mínimo de la serie) ÷ (máximo de la serie − mínimo de la serie)",
        ),
      },
      {
        titulo: tx("Cómo usarlo"),
        texto: [
          tx(
            "Un pétalo corto en Mediocampo con pétalos largos en Defensa y Ataque suele decir que el equipo pierde la posesión aunque tenga buenos jugadores en los extremos del campo: es el primer sitio donde mirar en Equipo, en su panel Cuello de botella. Al pasar el cursor por un pétalo, el globo explica por qué está en ese valor con los números reales.",
          ),
        ],
      },
    ],
  },
  {
    id: "club",
    grupo: tx("Club"),
    titulo: tx("Club y cuerpo técnico"),
    ruta: "/club",
    resumen: tx(
      "Quién trabaja para ti, qué aporta cada empleado y cómo está el ambiente del club.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Espíritu del equipo: de «Como en la Guerra Fría» (0) a «Paraíso en la Tierra» (10). Influye en el mediocampo del partido.",
          ),
          tx(
            "Confianza: de «Inexistente» (0) a «Desmedida» (9). Influye en el ataque.",
          ),
          tx(
            "Cuerpo técnico: entrenador, ayudantes y especialistas (médico, psicólogo deportivo y demás), con su nivel y qué efecto tiene cada uno.",
          ),
          tx(
            "Evolución del personal: cómo cambió el nivel del cuerpo técnico semana a semana.",
          ),
          tx("Socios y ánimo de la afición, con su historia."),
        ],
      },
      {
        titulo: tx("Cómo leerlo"),
        texto: [
          tx(
            "El espíritu y la confianza no son adornos: entran en los ratings de cada partido. Una caída de espíritu antes de un partido importante es una señal para revisar la actitud o las decisiones recientes. El cuerpo técnico, por su parte, cuesta sueldo cada semana: la pantalla explica qué aporta cada empleado para que puedas juzgar si compensa.",
          ),
          tx(
            "Alertas vigila tres huecos habituales: no tener médico, no tener psicólogo deportivo y tener los ayudantes de entrenador por debajo del nivel de referencia.",
          ),
        ],
      },
    ],
  },
  {
    id: "equipo",
    grupo: tx("Club"),
    titulo: tx("Habilidades"),
    ruta: "/overview",
    resumen: tx(
      "La media de la plantilla semana a semana: si el equipo mejora, envejece o se encarece.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Habilidades: la media de las siete habilidades de la plantilla, cada semana.",
          ),
          tx(
            "Experiencia y Fidelidad, en la misma escala de 0 a 20 que las habilidades.",
          ),
          tx("Resistencia y Forma, en su propia escala corta (de 1 a 9)."),
          tx(
            "Salario medio, TSI medio, suma de TSI y salario por punto de TSI.",
          ),
          tx(
            "HTMS y HTMS28 de la plantilla: lo que vale hoy y lo que valdría a los 28.",
          ),
          tx(
            "La plantilla por líneas del campo: Portería, Defensa Central, Defensa Lateral, Mediocentro, Extremo y Delantero.",
          ),
        ],
      },
      {
        titulo: tx("La línea de los 11 mejores"),
        texto: [
          tx(
            "En salario, TSI y suma de TSI hay dos líneas: la plantilla completa y los 11 jugadores de más TSI. La media de toda la plantilla la arrastran suplentes y canteranos; el once que juega se comporta distinto. El hueco entre las dos líneas va sombreado porque es exactamente la brecha entre titulares y resto.",
          ),
          tx(
            "En el salario por punto de TSI no hay sombreado: ahí las líneas se cruzan y el área entre ellas no significa nada. Los jugadores con TSI 0 (canteranos sin índice todavía) no cuentan en ese cociente, pero sí en las medias.",
          ),
        ],
      },
      {
        titulo: tx("Cómo usarlo"),
        texto: [
          tx(
            "Si la suma de TSI sube pero el HTMS28 baja, estás comprando rendimiento de hoy a costa de futuro (jugadores mayores). Si el salario por punto de TSI de los 11 mejores sube semana a semana, cada punto de calidad te está costando más: es momento de revisar renovaciones y ventas.",
          ),
        ],
      },
    ],
  },
  {
    id: "jugadores",
    grupo: tx("Club"),
    titulo: tx("Jugadores"),
    ruta: "/team",
    resumen: tx(
      "La tabla maestra de la plantilla y la ficha de cada jugador, presente y pasado.",
    ),
    secciones: [
      {
        titulo: tx("La tabla"),
        texto: [
          tx(
            "Todos los jugadores con sus habilidades, edad, TSI, salario, forma, resistencia, experiencia, especialidad, lesiones y estado en el mercado. Se ordena por cualquier columna y cada nombre abre su ficha. Sirve como punto de partida para cualquier pregunta sobre un jugador concreto.",
          ),
        ],
      },
      {
        titulo: tx("La ficha de un jugador actual"),
        puntos: [
          tx(
            "Momento de la carrera: en qué etapa está según su edad y su evolución.",
          ),
          tx("Habilidades con su nivel en número y en palabra."),
          tx(
            "Estado y contrato: forma, resistencia, lesión, sueldo y si está en el mercado.",
          ),
          tx(
            "Mejores posiciones: dónde rinde más según el rendimiento en el puesto.",
          ),
          tx("Precio de compra y carácter (simpatía, agresividad y honradez)."),
          tx(
            "Su TSI y su salario frente al resto de la plantilla, y cuánto paga por punto de TSI.",
          ),
          tx(
            "Evolución de habilidades, TSI y salario, HTMS y rating por partido.",
          ),
        ],
      },
      {
        titulo: tx("La ficha de un ex jugador"),
        texto: [
          tx(
            "Quien ya se fue conserva su ficha económica: tiempo en el club, entrenamiento que recibió según sus subidas, intentos de venta, desglose del salario acumulado y el cálculo de lo que dejó (ganancia y ROI). Es la vista individual de Transferencias.",
          ),
        ],
      },
      {
        titulo: tx("Juveniles"),
        texto: [
          tx(
            "Los canteranos de la academia no tienen ficha propia ni enlace: se estudian en Juveniles, donde está todo lo que se sabe de ellos.",
          ),
        ],
      },
    ],
  },
  {
    id: "habilidades",
    grupo: tx("Club"),
    titulo: tx("Equipo"),
    ruta: "/skills",
    resumen: tx(
      "Qué tiene la plantilla habilidad por habilidad, qué hueco deja cada titular si falta y qué sector te frena frente a tu serie.",
    ),
    secciones: [
      {
        titulo: tx("Qué pregunta responde"),
        texto: [
          tx(
            "Tres preguntas que ni la ficha de un jugador ni el plan de entrenamiento contestan: qué tiene la plantilla entera, dónde se queda corta si falta un titular y qué subida de habilidad rinde más en el campo.",
          ),
        ],
      },
      {
        titulo: tx("Indicadores"),
        puntos: [
          tx(
            "Mejor cubierto: el puesto donde menos rendimiento pierdes si falta el mejor titular.",
          ),
          tx("Hueco más serio: el puesto donde más pierdes."),
          tx(
            "Cuello de botella: el sector con menos ventaja sobre el mejor rival de tu serie.",
          ),
          tx(
            "Especialistas: cuántos jugadores tienen especialidad y cuáles, con su ícono.",
          ),
        ],
      },
      {
        titulo: tx("Mapa de la plantilla"),
        texto: [
          tx(
            "Cada jugador y su nivel en las siete habilidades (Portería, Defensa, Jugadas, Lateral, Pases, Anotación y Balón parado), agrupados por puesto. Cuanto más oscura la celda, más nivel; el borde marca la habilidad principal de su puesto. Al pasar el cursor por un número sale el nivel en palabra. Se puede ver el último once, toda la plantilla o sólo los sanos.",
          ),
          tx(
            "Se lee en dos direcciones. En horizontal, qué ofrece un jugador además de su puesto (un Defensa Central con Jugadas 12 puede cubrir el medio). En vertical, cuántos jugadores tienes de verdad en una habilidad.",
          ),
        ],
      },
      {
        titulo: tx("Profundidad: la formación"),
        texto: [
          tx(
            "Arranca en la formación del último partido oficial, que siempre se indica con su fecha y su reparto («5-3-2 con 3 Defensas Centrales y 1 Mediocentro»). Puedes elegir otra con los mismos mandos que Alineación: Formación, Defensas Centrales y Mediocentros. Con otra formación, los titulares reales siguen en su puesto (los mejores si sobran plazas) y cada plaza libre la ocupa, de una en una, el jugador sano que más rinde en ella. Así, al pasar de 3 a 2 Defensas Centrales, el tercero se queda en el banquillo y pasa a contar como recambio.",
          ),
        ],
      },
      {
        titulo: tx("Profundidad: el cálculo"),
        texto: [
          tx(
            "Para cada puesto de la formación se compara al mejor titular con el mejor jugador del banquillo, que es quien entraría de verdad si el titular falta por lesión, venta o sanción. No se compara con el segundo mejor de la plantilla, porque ése suele ser titular también: con tres Defensas Centrales entra el cuarto, con dos Delanteros el tercero.",
          ),
        ],
        puntos: [
          tx(
            "Los candidatos se ordenan por rendimiento en el puesto (el de Posiciones), no por una sola habilidad: un Delantero también necesita Pases.",
          ),
          tx("No cuenta quien esté lesionado."),
          tx(
            "No cuenta quien no llegue a débil (4) en la habilidad principal del puesto: un jugador de campo con Portería 1 no es recambio de portero aunque su forma le dé más rendimiento que a un veterano.",
          ),
          tx(
            "Si el mismo jugador es el primer recambio de varios puestos se avisa, porque no puede tapar dos a la vez, y se dice quién entraría después.",
          ),
        ],
        formula: tx(
          "pierdes = 1 − (rendimiento del suplente ÷ rendimiento del mejor titular)\n\n✅ Cubierto   menos de un 15 %\n⚠️ Cuidado    del 15 % a menos del 30 %\n🚨 Hueco      un 30 % o más, o nadie en el banquillo",
        ),
      },
      {
        titulo: tx("Profundidad: ejemplo"),
        texto: [
          tx(
            "En Defensas Centrales, el mejor titular rinde 19,1 y el mejor del banquillo 11,8: pierdes 1 − 11,8 ÷ 19,1 = 38 %, así que el estado es 🚨 Hueco. Si en Extremos el titular rinde 15,0 y el suplente 11,0, pierdes un 27 %: ⚠️ Cuidado.",
          ),
          tx(
            "Los cortes de 15 % y 30 % son una decisión de la app, no una regla de Hattrick. La tabla mide el impacto si falta el titular, no la probabilidad de que falte: un portero se lesiona mucho menos que un jugador de campo.",
          ),
        ],
      },
      {
        titulo: tx("Cuello de botella"),
        texto: [
          tx(
            "Tus tres sectores frente al mejor rival de tu serie en cada uno, con la media de los últimos 5 partidos oficiales de cada equipo. Los sectores no se comparan entre sí, porque Hattrick da el mediocampo en otra escala que las zonas de defensa y ataque: poner un 20 de mediocampo junto a un 80 de defensa diría que el mediocampo es una cuarta parte, y no es verdad.",
          ),
          tx(
            "Cada tarjeta enseña tu valor y el del mejor rival en barras, la ventaja en porcentaje y quién sostiene el sector en el once con su habilidad («Bordalás (Def 18)»). El cuello de botella es el sector donde menos ventaja le sacas al mejor rival, o donde más pierdes si vas por detrás. En la tabla de Profundidad sus puestos llevan 🍾: Porteros, Defensas Centrales y Defensas Laterales si es la defensa; Mediocentros si es el mediocampo; Extremos y Delanteros si es el ataque.",
          ),
        ],
        formula: tx(
          "ventaja = (tu media ÷ media del mejor rival − 1) × 100\n\nFuerte        ventaja de un 5 % o más\nSin ventaja   entre 0 % y 5 %\nPor detrás    negativa\nAquí se pierde  el sector más negativo",
        ),
      },
      {
        titulo: tx("Qué subir primero"),
        texto: [
          tx(
            "Debajo del cuello de botella, la app ordena qué nivel de qué jugador del once titular empuja más ese sector. Usa la tabla de contribución por puesto del Manual no Escrito: un nivel más de una habilidad suma su coeficiente en ese puesto (rebajado si hay varios en el mismo puesto), y se expresa como porcentaje de lo que el once ya aporta al sector. Por ejemplo, «Jugadas de Cobos: 12 → 13, el mediocampo del once sube un 2,9 %».",
          ),
          tx(
            "Es la mejor pista para elegir a quién entrenar o qué perfil fichar: una subida en el sector que te frena vale más que dos en uno donde ya sobras.",
          ),
        ],
      },
    ],
  },
  {
    id: "posiciones",
    grupo: tx("Club"),
    titulo: tx("Posiciones"),
    ruta: "/positions",
    resumen: tx(
      "Dónde rinde cada jugador: toda la plantilla comparada en un puesto y una orden individual.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        texto: [
          tx(
            "Eliges un puesto y su orden individual y la plantilla se ordena por rendimiento en él. Son 19 variantes de campo (Portero; Defensa Central normal, hacia la banda y ofensivo; Defensa Lateral normal, hacia el medio, ofensivo y defensivo; Mediocentro normal, hacia la banda, ofensivo y defensivo; Extremo normal, hacia el medio, ofensivo y defensivo; Delantero normal, defensivo y hacia la banda) más tres roles especiales: capitán, lanzador de faltas y lanzador de penaltis.",
          ),
        ],
      },
      {
        titulo: tx("Cómo se calcula el rendimiento en el puesto"),
        texto: [
          tx(
            "Cada puesto con su orden tiene una tabla de coeficientes del Manual no Escrito que dice cuánto aporta cada habilidad a cada sector del campo. Por ejemplo, un Mediocentro normal aporta al mediocampo con Jugadas × 1,00, a la defensa central con Defensa × 0,40 y al ataque central con Anotación × 0,22 y Pases × 0,33. Se suman todos los aportes y se dividen entre la suma de coeficientes, para que un puesto con más columnas no gane sólo por tenerlas. Después se ajusta por forma y resistencia.",
          ),
        ],
        formula: tx(
          "habilidad efectiva = nivel + ln(experiencia) × 4 ÷ 3 + fidelidad ÷ 19\n\naporte = Σ coeficiente × habilidad efectiva ÷ Σ coeficientes\n         × factor de forma × factor de resistencia\n\nfactor de forma       = ((forma − 0,5) ÷ 7) ^ 0,45\nfactor de resistencia = ((resistencia + 6,5) ÷ 14) ^ 0,6",
        ),
      },
      {
        titulo: tx("Los roles especiales"),
        puntos: [
          tx(
            "Capitán: 3 × liderazgo + 2 × experiencia. Según el Manual, elegirlo así da una experiencia de equipo igual o mayor que la del capitán automático.",
          ),
          tx("Lanzador de faltas: Balón parado + experiencia."),
          tx(
            "Lanzador de penaltis: combina experiencia, Balón parado y Anotación, con un bono si el jugador es Técnico.",
          ),
        ],
      },
      {
        titulo: tx("Cómo usarlo y hasta dónde vale"),
        texto: [
          tx(
            "Es la herramienta para decidir quién juega dónde y para descubrir jugadores que rinden en un puesto que no es el suyo. El mismo número alimenta Alineación y Equipo.",
          ),
          tx(
            "La matriz de coeficientes es comunitaria, no oficial de Hattrick. Mide el aporte posicional, no predice los ratings exactos de un partido: no incluye espíritu, confianza, táctica ni actitud.",
          ),
        ],
      },
    ],
  },
  {
    id: "alineacion",
    grupo: tx("Club"),
    titulo: tx("Alineación"),
    ruta: "/lineup",
    resumen: tx(
      "El mejor once posible, optimizando a la vez la formación, los jugadores y las órdenes individuales.",
    ),
    secciones: [
      {
        titulo: tx("Los dos modos"),
        puntos: [
          tx(
            "Mejor formación: prueba las diez formaciones del juego (5-5-0, 5-4-1, 5-3-2, 5-2-3, 4-5-1, 4-4-2, 4-3-3, 3-5-2, 3-4-3 y 2-5-3), cada una con su reparto predeterminado, y enseña la que más rinde.",
          ),
          tx(
            "Formación elegida: fijas una y dentro de ella cuántos Defensas Centrales y cuántos Mediocentros juegan por dentro; el resto va a las bandas. El motor optimiza jugadores y órdenes sin salir de esa estructura.",
          ),
        ],
      },
      {
        titulo: tx("Cómo se calcula"),
        texto: [
          tx(
            "Para cada pareja de jugador y casilla se prueban todas las órdenes individuales legales de esa casilla y se conserva la de mayor aporte. Después, el algoritmo húngaro asigna once jugadores distintos a las once casillas maximizando la suma total. En modo Mejor formación se repite para las diez y gana la de mayor suma.",
          ),
        ],
        formula: tx(
          "max Σ aporte(jugador, casilla, orden)\n\nsujeto a: cada jugador en una casilla como mucho\n          cada casilla con exactamente un jugador\n          cada orden legal para su casilla\n          las órdenes que fijaste, respetadas",
        ),
      },
      {
        titulo: tx("Tus mandos"),
        puntos: [
          tx(
            "Fijar la orden de una casilla: la orden queda atada a la casilla, no al jugador, y el motor elige quién la juega mejor.",
          ),
          tx(
            "Sacar jugadores del reparto (lesionados, sancionados o para probar): el once se vuelve a resolver entero sin ellos.",
          ),
          tx(
            "Los lesionados de una semana o más quedan fuera automáticamente; un magullado sigue disponible.",
          ),
          tx(
            "Cambiar de formación o de reparto limpia las órdenes fijadas, porque las casillas ya no representan lo mismo.",
          ),
        ],
      },
      {
        titulo: tx("Qué más enseña"),
        puntos: [
          tx("Banquillo: los siguientes mejores."),
          tx("Ranking de formaciones: cuánto rinde cada una con tu plantilla."),
          tx(
            "Espíritu de Equipo por Actitud: cómo cambia el once con cada combinación.",
          ),
          tx(
            "Calificación por sector: el desglose del once elegido, como diagnóstico.",
          ),
          tx(
            "Tu alineación contra la propuesta: qué cambia entre lo que mandaste a Hattrick y lo que recomienda el motor.",
          ),
        ],
      },
      {
        titulo: tx("Hasta dónde vale"),
        texto: [
          tx(
            "El objetivo es la suma del aporte posicional, no los ratings de partido ni el resultado contra un rival concreto. La «calificación total» es una suma de aportes normalizados, no una predicción oficial. Para preparar un partido concreto, combina la propuesta con la ficha del rival.",
          ),
        ],
      },
    ],
  },

  // ── Desarrollo ───────────────────────────────────────────────────────────
  {
    id: "entrenamiento",
    grupo: tx("Desarrollo"),
    titulo: tx("Entrenamiento"),
    ruta: "/training",
    resumen: tx(
      "Cuánto falta para la siguiente subida de cada jugador y si estás entrenando lo que conviene.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Entrenamiento actual: tipo, intensidad y la parte dedicada a resistencia.",
          ),
          tx("Entrenador y asistentes, con su efecto sobre la velocidad."),
          tx(
            "Historial de la configuración semanal: qué se entrenó cada semana.",
          ),
          tx(
            "Subidas confirmadas: las que ya ocurrieron, detectadas comparando lecturas.",
          ),
          tx(
            "Previsión de subidas: cuánto le falta a cada jugador para el siguiente nivel.",
          ),
          tx(
            "Experiencia, fidelidad y resistencia, cada una con su propio modelo.",
          ),
          tx(
            "Entrenamiento decidido a posteriori: con los minutos reales de la semana, qué entrenamiento habría aprovechado mejor esos mismos partidos.",
          ),
        ],
      },
      {
        titulo: tx("Semanas hasta el próximo nivel"),
        texto: [
          tx(
            "La velocidad de entrenamiento de un jugador es el producto de todo lo que la afecta: el tipo de entrenamiento, el nivel del entrenador, los asistentes, la intensidad, la parte que se va a resistencia y la exposición (los minutos reales jugados en un puesto que entrena ese tipo, frente a un partido completo). El esfuerzo para pasar de un nivel al siguiente crece con el nivel según una curva en dos tramos, y la edad frena según un «reloj» que avanza más despacio cuanto mayor es el jugador.",
          ),
        ],
        formula:
          "K = K_entrenamiento × K_entrenador × K_asistentes\n    × intensidad × (1 − %resistencia) × exposición\n\nsemanas = 16 × ( reloj⁻¹( reloj(edad) + [F(n+1) − F(n)] ÷ K ) − edad )",
      },
      {
        titulo: tx("Cómo leer las constantes"),
        puntos: [
          tx(
            "K_entrenamiento: cuanto más alto, más rápido sube esa habilidad. Balón parado es el más alto porque su habilidad pesa menos en el campo, no porque entrene mejor.",
          ),
          tx(
            "K_asistentes: una base más un bono por cada nivel, sumando los niveles de todos los asistentes hasta un tope.",
          ),
          tx("Un año de Hattrick son 112 días, es decir 16 semanas."),
          tx(
            "El subnivel exacto no se publica: si no se conoce, se supone que el jugador acaba de subir.",
          ),
        ],
      },
      {
        titulo: tx("Resistencia"),
        texto: [
          tx(
            "La resistencia va por un modelo propio: una tabla de la comunidad da el nivel al que tiende un jugador según su edad (de 17 a 36 años) y el porcentaje REAL de entrenamiento de resistencia. Ese porcentaje real es la intensidad multiplicada por la parte dedicada: un club al 40 % de intensidad con la mitad en resistencia pone un 20 %, no un 50 %. Es un nivel de equilibrio, no una predicción semana a semana.",
          ),
        ],
      },
      {
        titulo: tx("Experiencia y fidelidad"),
        texto: [
          tx(
            "La experiencia sube con puntos que da cada partido según su tipo (los importantes dan más). La tabla de puntos por nivel no la publica Hattrick: está calibrada con las subidas observadas en tu propio histórico. La fidelidad crece con las semanas en el club siguiendo una tabla de la comunidad, y aporta hasta un nivel más en todas las habilidades de campo.",
          ),
        ],
      },
      {
        titulo: tx("Hasta dónde vale"),
        texto: [
          tx(
            "Los coeficientes son la estimación pública de la comunidad (HT-Tools), no constantes oficiales de Hattrick, y no se ajustan con tus datos. Por encima de 34 años la tabla de edad se prolonga con su último tramo. Úsalo para comparar y planificar, no como una fecha exacta.",
          ),
        ],
      },
    ],
  },
  {
    id: "juveniles",
    grupo: tx("Desarrollo"),
    titulo: tx("Juveniles"),
    ruta: "/academy",
    resumen: tx(
      "Quién merece plaza en la academia, a quién no puedes dejar pasar, cómo entrenarlos y si la academia sale a cuenta.",
    ),
    secciones: [
      {
        titulo: tx("Qué se sabe de un canterano"),
        texto: [
          tx(
            "De cada canterano se conoce su nivel actual y su techo en cada habilidad sólo cuando los ojeadores o el entrenamiento los revelan. La app nunca presenta una suposición como si fuera evidencia: un techo sin revelar se trata como desconocido, y la mejor habilidad y la categoría sólo salen de techos revelados.",
          ),
        ],
      },
      {
        titulo: tx("Categorías"),
        texto: [
          tx(
            "La categoría sale del mejor techo REVELADO, en la escala juvenil:",
          ),
        ],
        puntos: [
          tx("Crack: techo 8 o más. Proyecto de titular."),
          tx("Promesa: techo 7. Merece plaza de entrenamiento."),
          tx("Aceptable: techo 6. Puede servir de suplente."),
          tx("Vendible: techo 5. Se vende sin pena."),
          tx("Fontanero: techo 4 o menos."),
          tx(
            "Sin ojear: todavía no se ha revelado ningún techo, así que no hay veredicto.",
          ),
        ],
      },
      {
        titulo: tx("La asimetría que lo decide todo"),
        texto: [
          tx(
            "Revelar una habilidad sólo puede SUBIR el mejor techo, nunca bajarlo. Por eso un veredicto bueno (crack, promesa o aceptable) ya es firme, y uno malo (vendible o fontanero) es provisional mientras quede una sola habilidad por revelar: un 8 escondido convierte a un fontanero en un crack, y despedir no se deshace. La app no recomienda despedir sobre una lectura incompleta.",
          ),
          tx(
            "Cuando hace falta liberar una plaza, la pregunta no es «¿este chico es malo?» sino «¿quién es el último de la fila?»: se sugiere al que menos aporta al ranking de entrenamiento y, si empatan, al mayor, que tiene menos tiempo por delante.",
          ),
        ],
      },
      {
        titulo: tx("El plazo"),
        texto: [
          tx(
            "Un canterano puede quedarse en la academia hasta los 19 años (19 × 112 días). La app cuenta los días que quedan y, cuando faltan 21 o menos, lo marca como urgente: si no lo subes al primer equipo antes, lo pierdes. Alertas avisa también de los juveniles a punto de perderse.",
          ),
        ],
      },
      {
        titulo: tx("Qué entrenar en la academia"),
        texto: [
          tx(
            "El puntaje de cada habilidad suma, canterano por canterano, el peso del «peldaño» en que está ese chico para esa habilidad. Los peldaños van de excelente a desconocido, y cada uno vale β = 3 veces el siguiente, así que un canterano excelente pesa mucho más que varios dudosos. Quien ya tocó techo en esa habilidad pesa cero. El total se divide entre 16, el tamaño máximo de una academia, para que el puntaje no suba sólo por tener pocos canteranos.",
          ),
        ],
        formula: tx(
          "puntaje(habilidad) = Σ peso(peldaño del canterano) ÷ 16\n\npeso de cada peldaño = 3 × peso del peldaño siguiente\nal tope = 0",
        ),
      },
      {
        titulo: tx("El entrenamiento Individual"),
        texto: [
          tx(
            "Con Individual, Hattrick no entrena una habilidad fija por puesto: sortea una entre las útiles de ese puesto, y cada habilidad tiene su propio ritmo. La secundaria recibe dos tercios del principal; si repite la misma habilidad que el principal, sólo la mitad de esos dos tercios.",
          ),
        ],
        formula: tx(
          "secundaria distinta:  100 % + 66,7 % = 166,7 %\nsecundaria repetida:  100 % + 66,7 % × 50 % = 133,3 %",
        ),
      },
      {
        titulo: tx("Ojeadores y rentabilidad"),
        texto: [
          tx(
            "Cada ojeador tiene su cuenta: semanas contratado (sólo cuentan las completas), lo que ha costado cada canterano que trajo y los días desde su último fichaje. Sirve para comparar ojeadores antes de que haya ninguna venta. La academia entera se juzga igual: Alertas dice si ha sido rentable o si todavía no ha recuperado la inversión.",
          ),
        ],
      },
    ],
  },
  {
    id: "transferencias",
    grupo: tx("Desarrollo"),
    titulo: tx("Transferencias"),
    ruta: "/transfers/balance",
    resumen: tx(
      "Qué dejó de verdad cada jugador que pasó por el club, de la compra a la venta, sueldos incluidos.",
    ),
    secciones: [
      {
        titulo: tx("Qué pregunta responde"),
        texto: [
          tx(
            "«¿Gano o pierdo dinero con el mercado?». El precio de venta menos el de compra engaña: durante el tiempo en el club el jugador cobró su sueldo, el listado costó y el agente se lleva una comisión. Esta pantalla lo suma todo.",
          ),
        ],
      },
      {
        titulo: tx("Cómo se calcula"),
        formula: tx(
          "venta neta = precio de venta × (1 − % del agente)\ncoste      = compra + salarios acumulados + listados\n\nganancia = venta neta − coste + reventa\nROI      = ganancia ÷ coste × 100",
        ),
        puntos: [
          tx(
            "La comisión del agente depende de los días que el jugador estuvo en el club; los canteranos pagan una tarifa plana.",
          ),
          tx(
            "Reventa es la comisión que llega cuando el nuevo club de un ex jugador tuyo lo vuelve a vender.",
          ),
          tx(
            "Los listados cuestan cada vez que pones a alguien en el mercado, aunque no se venda.",
          ),
        ],
      },
      {
        titulo: tx("Los sueldos de antes de HT Lens"),
        texto: [
          tx(
            "De cuatro de las cinco partes del saldo (compra, venta, agente y listados) se recupera la historia completa. El sueldo no: Hattrick no publica lo que cobraba un jugador hace años. Para esas etapas el sueldo se estima con el TSI y la edad del jugador, ajustado con las lecturas reales de tu propio club; si hay al menos una lectura real de ese jugador, se usa como ancla y el error baja mucho.",
          ),
        ],
        formula: tx("log(sueldo) = a + b × log(TSI) + c × edad"),
      },
      {
        titulo: tx("Tres estados, nunca dos"),
        texto: [
          tx(
            "Cada cifra dice si es medida, estimada o desconocida, y los totales se pueden ver con todo, sin lo desconocido o sólo con lo medido. Mezclarlas sin decirlo daría un saldo que parece exacto y no lo es.",
          ),
        ],
      },
      {
        titulo: tx("Los cortes"),
        texto: [
          tx(
            "Saldo y ROI por temporada, por semana de compra y de venta, por hora de cierre de la puja, por edad al vender, por entrenamiento al vender y por habilidad más alta. Sirven para descubrir patrones: a qué edad vendes mejor, qué entrenamiento revaloriza más o a qué hora cierran tus mejores ventas.",
          ),
          tx(
            "«Intentos de transferencia» guarda cada vez que pusiste a un jugador en el mercado con su resultado, aunque no se vendiera.",
          ),
        ],
      },
    ],
  },

  // ── Competición ──────────────────────────────────────────────────────────
  {
    id: "partidos",
    grupo: tx("Competición"),
    titulo: tx("Partidos"),
    ruta: "/matches",
    resumen: tx(
      "Por qué se ganó o se perdió: generación de ocasiones frente a definición, sector por sector.",
    ),
    secciones: [
      {
        titulo: tx("La idea central"),
        texto: [
          tx(
            "Un marcador dice quién ganó, no por qué. «Llegamos nueve veces y metimos una» y «llegamos tres y metimos dos» son el mismo 1-2 y piden decisiones opuestas: la primera un delantero, la segunda mediocampo. Por eso la pantalla separa la generación de ocasiones (mediocampo y táctica) de la definición (anotación y suerte).",
          ),
        ],
      },
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx("Resumen: ganados, empatados y perdidos, goles y HatStats medio."),
          tx(
            "Conversión: ocasiones propias y del rival, goles y porcentaje de conversión, por zona.",
          ),
          tx(
            "Evolución de los ratings partido a partido: mediocampo, defensa y ataque.",
          ),
          tx("Local y visitante por separado."),
          tx(
            "Historial con fecha, rival, torneo con el nombre real de la copa, resultado y HatStats propio y rival.",
          ),
        ],
      },
      {
        titulo: tx("HatStats"),
        texto: [
          tx(
            "Un índice de la comunidad que resume la fuerza mostrada en un partido. El mediocampo cuenta triple porque decide la posesión, no porque valga tres veces un gol.",
          ),
        ],
        formula: tx(
          "HatStats = 3 × mediocampo\n         + (defensa derecha + central + izquierda)\n         + (ataque derecho + central + izquierdo)",
        ),
      },
      {
        titulo: tx("El análisis de un partido"),
        texto: [
          tx(
            "Al abrir un partido se ve el mapa de sectores sobre la cancha: cada zona tuya enfrentada a la del rival que la cubre, con quién ganó cada duelo. Las bandas van cruzadas, como en el campo: tu ataque por la izquierda se enfrenta a su defensa por la derecha.",
          ),
        ],
      },
      {
        titulo: tx("Filtros y datos"),
        texto: [
          tx(
            "Se filtra por temporada y se pueden incluir los amistosos. Torneos, duelos, escaleras y partidos de preparación no aparecen nunca. La primera sincronización trae la historia completa del equipo con el detalle de cada partido; después se añaden sólo los nuevos. Con muy pocas ocasiones, la conversión es ruido: la pantalla lo tiene en cuenta antes de sacar conclusiones.",
          ),
        ],
      },
    ],
  },
  {
    id: "pronostico",
    grupo: tx("Competición"),
    titulo: tx("El pronóstico de partido"),
    resumen: tx(
      "Cómo se llega de los ratings de los partidos jugados a «34 % victoria, 28 % empate, 38 % derrota». Lo usan Dashboard, Liga, Copa y Rivales.",
    ),
    secciones: [
      {
        titulo: tx("En una frase"),
        texto: [
          tx(
            "Un partido de Hattrick es un conjunto de duelos localizados. Si se mide qué parte de cada duelo se lleva cada equipo y se sabe cuánto pesa cada uno, se puede estimar cuántos goles marcará cada lado, y de ahí la probabilidad de cada marcador y de cada resultado. Los pesos salen de dos regresiones ajustadas sobre 5.232 partidos de liga reales de 979 equipos de cinco países.",
          ),
        ],
      },
      {
        titulo: tx("1. Describir a cada equipo"),
        texto: [
          tx(
            "Los ratings de un partido futuro no existen todavía, así que primero se resume cómo suele salir cada equipo en sus nueve ratings (mediocampo, tres defensas, tres ataques y los dos de balón parado), con los partidos de una sola competición: la liga (con promoción y Hattrick Masters) o la copa, porque un equipo no juega igual en las dos. Basta un partido previo por lado.",
          ),
        ],
        puntos: [
          tx(
            "Promedio (por defecto): cómo suele salir. Es el que menos se equivoca.",
          ),
          tx("Máximo: de lo que es capaz en cada zona."),
          tx(
            "Máximo por carril: de lo que es capaz por cualquiera de los tres carriles.",
          ),
          tx("Último partido: lo del último día, sin resumir."),
          tx(
            "Alineación enviada (sólo tu lado): los ratings que Hattrick calcula para las órdenes que ya mandaste.",
          ),
        ],
      },
      {
        titulo: tx("2. La sede"),
        texto: [
          tx(
            "La ventaja de campo va dentro de los ratings: el mediocampo de un equipo en casa sale de media un 17,8 % más alto que fuera. Como el promedio mezcla partidos de casa y fuera, el mediocampo resumido se lleva a la sede del partido que viene según cuántos partidos jugó cada equipo en casa. Sin esta corrección el motor rebajaba al local.",
          ),
        ],
      },
      {
        titulo: tx("3. El duelo"),
        texto: [
          tx(
            "Un rating suelto no dice nada: un ataque de 12 es excelente contra una defensa de 6 y poca cosa contra una de 20. Cada duelo se mide como la fracción que te llevas, con los carriles cruzados.",
          ),
        ],
        formula: tx(
          "p = A ÷ (A + B)    A tu rating, B el suyo\n\n0,5 igualdad · 0,7 dominio claro · 0,3 dominado\n\ntu ataque izquierdo  ↔ su defensa derecha\ntu ataque central    ↔ su defensa central\ntu ataque derecho    ↔ su defensa izquierda\ntu mediocampo        ↔ su mediocampo",
        ),
      },
      {
        titulo: tx("4. De los duelos a los goles"),
        texto: [
          tx(
            "Una regresión de Poisson (la herramienta estándar para contar goles) estima λ, los goles esperados de cada lado, en dos sumandos. El juego abierto depende del duelo de mediocampo y de la media de los tres carriles de ataque (30 % cada banda y 40 % el centro, con un exponente común de 3,39, así que el carril mejor manda). El balón parado va aparte, con una dependencia del mediocampo tres veces menor. De media, el 72 % de los goles esperados sale del juego abierto y el 28 % del balón parado.",
          ),
        ],
        formula: tx(
          "λ = (juego abierto + balón parado) × factor de la táctica",
        ),
      },
      {
        titulo: tx("5. La táctica"),
        texto: [
          tx(
            "Los ratings dicen con qué se juega, no cómo. Presionar recorta ocasiones a los dos: en los partidos donde un lado presionaba, el modelo prometía 2,00 goles y se marcaban 1,45. Contraataques, Jugar creativamente y Atacar por las bandas marcan algo más de lo previsto. Cada táctica multiplica los goles esperados de quien la juega. Tu táctica se toma de las órdenes si ya las mandaste; la del rival se pondera según cuántas veces usó cada una.",
          ),
        ],
      },
      {
        titulo: tx("6. Del gol al resultado"),
        texto: [
          tx(
            "Con los dos λ se construye una rejilla de marcadores: la probabilidad de un 2-1 es «tú marcas 2» por «él marca 1». Sumando la rejilla en tres montones salen victoria, empate y derrota. En copa no hay empate (hay prórroga y penaltis), así que el empate se reparte entre los dos en proporción. El «resultado más probable» es sólo la casilla más alta, y casi nunca pasa del 12 %.",
          ),
        ],
      },
      {
        titulo: tx("7. La segunda opinión"),
        texto: [
          tx(
            "Una regresión ordinal aprende directamente de quién ganó, con los nueve duelos (incluidos los defensivos). Los dos modelos se equivocan en sitios distintos, así que se mezclan: 80 % el de goles y 20 % el de resultado. El 80 % es el mínimo de error y el último punto donde el empate sigue calibrado.",
          ),
        ],
      },
      {
        titulo: tx("8. Cómo se comprobó"),
        puntos: [
          tx(
            "Evaluación con origen móvil: se ajusta con los partidos anteriores a un corte y se predicen los siguientes, que el modelo no ha visto, en cinco cortes.",
          ),
          tx(
            "Log-loss 0,6328 frente a 1,0986 de no saber nada; acierta el 73 % de los partidos frente al 50 % de acertar siempre lo más común.",
          ),
          tx(
            "Con el promedio de los partidos anteriores, que es lo que usa la pantalla: log-loss 0,6924 y 71,3 % de acierto. La diferencia es el precio de no conocer la alineación.",
          ),
          tx("Copa validada aparte: 88,4 % de acierto en quién pasa."),
          tx(
            "Las tres probabilidades están calibradas: cuando dice 70 %, ocurre cerca del 70 % de las veces.",
          ),
        ],
      },
      {
        titulo: tx("9. Hasta dónde vale"),
        puntos: [
          tx(
            "No conoce la alineación del domingo del rival, lesiones, sanciones, actitud ni clima.",
          ),
          tx(
            "Promete de media un 14,5 % de empates donde ocurren un 13,0 %: si el empate sale como opción más gorda, descuéntale algo.",
          ),
          tx(
            "El coeficiente del balón parado no se lee literal: comparte el 62 % de su varianza con los ataques, así que no justifica por sí solo fichar un especialista.",
          ),
          tx(
            "Un rival que acaba de reforzarse tarda unas jornadas en reflejarse en su promedio.",
          ),
        ],
      },
    ],
  },
  {
    id: "liga",
    grupo: tx("Competición"),
    titulo: tx("Liga"),
    ruta: "/league",
    resumen: tx(
      "Cómo va la temporada y cómo puede acabar, como distribución de probabilidades y no como un solo número.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx("Clasificación oficial en total, en casa y fuera."),
          tx(
            "Distribución de la posición final: la probabilidad de acabar en cada puesto.",
          ),
          tx(
            "Pronóstico por equipo: puntos esperados y probabilidad de título y de acabar entre los cuatro primeros.",
          ),
          tx("Próximo partido con su pronóstico."),
          tx(
            "Límites matemáticos de posición: el mejor y el peor puesto todavía posibles.",
          ),
          tx(
            "Historial de la serie: la evolución real de puestos y puntos jornada a jornada.",
          ),
          tx("Calendario completo."),
          tx(
            "Comparativa de liga: TSI de tu plantilla frente al resto y la comparativa de rivales (TSI, forma, resistencia, experiencia y mejor jugador).",
          ),
          tx(
            "Mejor alineación: el mejor once de la jornada o de la temporada, con calificaciones reales.",
          ),
        ],
      },
      {
        titulo: tx("La simulación de temporada"),
        texto: [
          tx(
            "La respuesta a «¿en qué puesto acabo?» es una distribución. Se simula el resto de la temporada miles de veces y se cuenta en qué puesto acaba cada equipo. Quién gana cada partido pendiente lo decide el mismo motor de zonas del pronóstico de partido, con los ratings de los ocho equipos; el marcador con el que gana sale de la fuerza de ataque y defensa de la temporada. Así los dos paneles de Proyección y el pronóstico no pueden decir cosas distintas del mismo encuentro.",
          ),
          tx(
            "El modelo de goles de la temporada queda de respaldo, para los cruces a los que les falten ratings de algún lado. Esa fuerza se encoge hacia la media de la liga con K = 5 para no fiarse de pocos partidos, y el local lleva una ventaja de 1,20 sobre sus goles esperados.",
          ),
        ],
        formula: tx(
          "quién gana   terna del motor de zonas (ver «El pronóstico de partido»)\n\nsin ratings  λ local     = ataque_i × defensa_j × media de la liga × 1,20\n             λ visitante = ataque_j × defensa_i × media de la liga\n\nel marcador  fuerza = (goles + 5 × media) ÷ (partidos + 5)",
        ),
      },
      {
        titulo: tx("Cómo se resume cada equipo"),
        texto: [
          tx(
            "Un selector elige con qué resumen de los partidos jugados se mide a los ocho equipos (promedio, máximo, máximo por carril o último partido; ver «El pronóstico de partido»). Mueve los puntos esperados, la distribución y los límites. El próximo partido, en cambio, se pronostica con alineaciones concretas: la tuya enviada si ya mandaste órdenes, o la de tu último partido, y la del último partido del rival.",
          ),
        ],
      },
      {
        titulo: tx("Cómo leerlo"),
        texto: [
          tx(
            "«Terminar 1º» no es lo mismo que ascender: el ascenso depende también del ranking nacional de campeones, que Hattrick no publica. Los límites matemáticos, en cambio, son seguros pase lo que pase. Alertas vigila el descenso directo, la promoción, la carrera por el título, el ataque y la defensa por debajo de la media, y si eres favorito o no en el próximo partido.",
          ),
          tx(
            "Si Hattrick sustituye a un equipo de la serie a mitad de temporada, la app une su historia con la del equipo nuevo para que la clasificación y el historial sigan siendo coherentes.",
          ),
        ],
      },
    ],
  },
  {
    id: "copa",
    grupo: tx("Competición"),
    titulo: tx("Copa"),
    ruta: "/cup",
    resumen: tx(
      "Qué te juegas en el siguiente cruce: premios que quedan, qué pasa si ganas y a qué copa vas si pierdes.",
    ),
    secciones: [
      {
        titulo: tx("Las copas"),
        texto: [
          tx(
            "La copa principal puede ser nacional (con el nombre de tu país, por ejemplo «Copa Colombia») o divisional para las divisiones más bajas. Quien pierde en las primeras rondas no siempre queda fuera: pasa a una de las tres copas Desafío (Esmeralda, Rubí o Zafiro, según la ronda en que cayó) y, desde ellas, a la de Consuelo. Cada país pone nombre propio a sus copas, como «Copa Cocuy Rubí».",
          ),
        ],
      },
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Estado: si sigues en competencia, la ronda oficial y las victorias que faltan para el título.",
          ),
          tx(
            "Qué ocurre con el próximo resultado: si ganas, qué premio aseguras; si pierdes, a qué copa pasas o si se cierra tu temporada de copa.",
          ),
          tx(
            "Probabilidad de avanzar, con el mismo motor de pronóstico (en copa sin empate).",
          ),
          tx(
            "Impacto del tipo de copa: los premios de la copa en que estás frente a las demás.",
          ),
          tx(
            "Próximo partido, su ingreso esperado y la economía observada de la copa.",
          ),
          tx("Trayectoria de la temporada e historial."),
          tx(
            "Preparación para 120 minutos: resistencia de tus jugadores por si hay prórroga.",
          ),
          tx("Orden orientativo de penaltis."),
        ],
      },
      {
        titulo: tx("Los premios"),
        texto: [
          tx(
            "Los premios se publican en coronas suecas y la app los convierte a tu moneda. En la copa nacional principal van de 1.200.000 en la ronda de 512 a 15.000.000 para el campeón; en las copas Desafío nacionales y en la divisional principal, hasta 3.000.000; en la Desafío divisional, hasta 1.500.000. La de Consuelo sólo da el trofeo. La pantalla marca qué premios ya aseguraste, cuál es el siguiente hito y cuántas victorias hacen falta.",
          ),
        ],
      },
      {
        titulo: tx("Cómo decidir"),
        texto: [
          tx(
            "Con la probabilidad de avanzar y el premio del siguiente hito puedes valorar cuánto arriesgar: rotar para cuidar la liga, o jugar con el mejor once y actitud de partido importante. La economía de copa suma además la taquilla de los partidos en casa.",
          ),
        ],
      },
    ],
  },
  {
    id: "rivales",
    grupo: tx("Competición"),
    titulo: tx("Rivales"),
    ruta: "/rivals",
    resumen: tx(
      "Cómo llega el equipo que tienes enfrente, estudiado con las mismas herramientas que usas para el tuyo.",
    ),
    secciones: [
      {
        titulo: tx("Elegir rival"),
        texto: [
          tx(
            "Los rivales de liga y de las copas ya cruzados o programados esta temporada, separados por competición (incluido Hattrick Masters si lo juegas), o cualquier equipo por su ID.",
          ),
        ],
      },
      {
        titulo: tx("Qué hay en la ficha"),
        puntos: [
          tx("Tu TSI frente al suyo, con histograma de las dos plantillas."),
          tx(
            "Once probable y jugadores del rival identificados en sus alineaciones.",
          ),
          tx("Táctica habitual y formaciones que usa."),
          tx("Rotación del ataque: por qué lado suele cargar."),
          tx(
            "Sugerencia de marcaje al hombre: quién de los tuyos marcaría a quién.",
          ),
          tx(
            "Duelos por zona de la cancha: siete zonas tuyas frente a las suyas, con el método de resumen que elijas para cada lado.",
          ),
          tx("Pronóstico del partido."),
          tx("Fichajes recientes y actividad del manager."),
        ],
      },
      {
        titulo: tx("El marcaje al hombre"),
        texto: [
          tx(
            "Un Defensa Lateral, un Defensa Central o un Mediocentro pueden marcar a un Extremo, un Defensa Central o un Mediocentro rival. La combinación «cerca» (lateral sobre extremo, central sobre delantero, mediocentro sobre mediocentro) es la más eficiente; cualquier otra legal es «lejos» y rinde menos, pero sigue siendo válida.",
          ),
        ],
      },
      {
        titulo: tx("De dónde salen los datos"),
        texto: [
          tx(
            "Del rival sólo se usa lo que Hattrick publica: sus partidos ya jugados y su plantilla visible. Se pide en vivo cada vez que abres la ficha y no se guarda, por eso tarda unos segundos. Se analizan sus últimos partidos oficiales contra cualquier equipo, no sólo contra ti; con el selector de la esquina puedes mirar sus amistosos en su lugar (uno u otro, nunca mezclados). Duelos y escaleras no cuentan nunca.",
          ),
          tx(
            "De tu lado, la ficha puede usar la alineación que ya enviaste; del rival nunca, porque sus órdenes son privadas hasta que se juega.",
          ),
        ],
      },
    ],
  },

  // ── Negocio ──────────────────────────────────────────────────────────────
  {
    id: "economia",
    grupo: tx("Negocio"),
    titulo: tx("Economía"),
    ruta: "/economy",
    resumen: tx(
      "A dónde va tu dinero, si el club se sostiene sin vender y cuántas semanas aguanta la caja.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Finanzas de esta semana, con las categorías oficiales de Hattrick sin renombrar ni fundir.",
          ),
          tx(
            "Flujo: de dónde entra y a dónde va el dinero, en varias ventanas de tiempo.",
          ),
          tx("Balances acumulados."),
          tx("Ingresos y gastos por semana y por temporada."),
          tx(
            "Escenario de caja: la proyección, siempre aparte y marcada como escenario.",
          ),
          tx("Anomalías observadas: semanas que se salen de lo normal."),
        ],
      },
      {
        titulo: tx("La semana cerrada"),
        texto: [
          tx(
            "Las cifras semanales que da Hattrick corresponden a la semana que YA cerró, no a la del día en que se leen; la app las sitúa en su semana real. La semana en curso va aparte porque está a medias: por ejemplo, reporta taquilla 0 hasta que se juega el partido en casa. Hattrick sólo sirve la semana actual y la anterior, así que la historia más vieja vale lo que valió cada lectura guardada a tiempo.",
          ),
          tx(
            "El bono del patrocinador de la semana cerrada no llega desglosado: se deduce restando las partidas del total.",
          ),
        ],
      },
      {
        titulo: tx("Balance sin transferencias"),
        texto: [
          tx(
            "Responde «¿se sostiene el club sin vender a nadie?». Suma lo que entra de forma recurrente y resta lo que sale, con la media de las dos últimas semanas cerradas. La taquilla sólo entra los días de partido en casa (7 por temporada), así que se reparte entre las 16 semanas de la temporada para no hundir y levantar el número según el calendario.",
          ),
        ],
        formula: tx(
          "balance = patrocinios + taquilla semanal\n          − salarios − cuerpo técnico − estadio\n          − (juveniles + financieros)",
        ),
      },
      {
        titulo: tx("El escenario de caja"),
        texto: [
          tx(
            "Proyecta el saldo semana a semana con la estructura recurrente del club, sin compraventa de jugadores. Dice si la caja llega a cero en el horizonte elegido y en qué semana, con y sin contar la compraventa. Cuando hay suficiente historia se compara además con un modelo de series de tiempo y se enseñan rangos de incertidumbre.",
          ),
          tx(
            "El mismo número alimenta Dashboard, Economía y la alerta de déficit: las tres dicen siempre lo mismo.",
          ),
        ],
      },
      {
        titulo: tx("Alertas de economía"),
        puntos: [
          tx(
            "Déficit de fondo: el club pierde dinero cada semana sin contar transferencias.",
          ),
          tx(
            "Concentración de ingresos: demasiado dinero depende de una sola fuente.",
          ),
          tx("La caja va peor de lo que Hattrick esperaba."),
          tx("La peña de aficionados está encogiendo."),
          tx("Un jugador se lleva una parte excesiva de la nómina."),
        ],
      },
    ],
  },
  {
    id: "estadio",
    grupo: tx("Negocio"),
    titulo: tx("Estadio"),
    ruta: "/arena",
    resumen: tx(
      "Cuánta gente entra en cada partido, si el estadio se está llenando ahora y si compensa ampliar.",
    ),
    secciones: [
      {
        titulo: tx("Indicadores"),
        puntos: [
          tx("Aforo total."),
          tx("Ocupación media sobre los partidos analizados."),
          tx(
            "Ocupación de los últimos 3 partidos, cuántos se llenaron y la diferencia con la media.",
          ),
          tx("Partidos analizados y asientos vacíos de media."),
        ],
      },
      {
        titulo: tx("Ocupación por partido"),
        texto: [
          tx(
            "Una barra por partido en casa con el rival en el eje; al pasar el cursor, rival, torneo (con el nombre real de la copa), fecha, ocupación y asientos vendidos. Los tres últimos van en ámbar con su propia línea de media, junto a la media general: si la línea de los últimos está por encima, el estadio se está llenando ahora más que antes.",
          ),
        ],
        formula: tx("ocupación = entradas vendidas ÷ aforo total × 100"),
      },
      {
        titulo: tx("Filtros y reglas"),
        puntos: [
          tx(
            "Todos, oficiales o amistosos: un amistoso se llena de otra manera y mezclarlo esconde los que cuentan.",
          ),
          tx("Temporada, con el mismo selector que Partidos."),
          tx(
            "Si cambió el aforo, el conteo empieza desde el primer partido con el aforo actual: una ocupación medida contra el estadio de antes no dice nada del de ahora.",
          ),
          tx("Torneos, duelos, escaleras y preparación no cuentan nunca."),
        ],
      },
      {
        titulo: tx("¿Compensa ampliar?"),
        texto: [
          tx(
            "Primero compara tu reparto de asientos con el que la comunidad considera óptimo, porque es la proporción en que la demanda de cada sector suele llenarse a la vez: 62,5 % general, 25 % preferentes, 10 % tribunas y 2,5 % palcos. La columna «Para cuadrarlo» dice cuántos asientos sobran o faltan en cada sector.",
          ),
          tx(
            "Después evalúa tres ampliaciones (pequeña de 1.000 asientos, mediana de 2.500 y grande de 5.200), siempre con el reparto recomendado. Para cada una calcula la obra, el mantenimiento semanal, el ingreso extra por partido con tu llenado medio y el neto por temporada con 7 partidos en casa. Si con tu ocupación actual sobran asientos, lo dice claramente: ninguna ampliación paga ni su mantenimiento.",
          ),
        ],
      },
    ],
  },

  // ── Inteligencia ─────────────────────────────────────────────────────────
  {
    id: "sincronizacion",
    grupo: tx("Inteligencia"),
    titulo: tx("Sincronización"),
    ruta: "/sync",
    resumen: tx("El único lugar desde donde se traen datos de Hattrick."),
    secciones: [
      {
        titulo: tx("Cómo funciona"),
        texto: [
          tx(
            "Un botón para sincronizar, el progreso paso a paso mientras trabaja y, al terminar, «Lo que encontró»: cuántos jugadores, partidos, transferencias y lecturas nuevas se guardaron. La pantalla se queda abierta al acabar para que veas el resultado. Justo después se precalculan en segundo plano las pantallas más pesadas (liga, comparativa, economía, partidos), para que carguen al instante.",
          ),
          tx("Ver también «Conectar y sincronizar» en Empezar."),
        ],
      },
    ],
  },
  {
    id: "cambios",
    grupo: tx("Inteligencia"),
    titulo: tx("Cambios"),
    ruta: "/news",
    resumen: tx(
      "Lo que movió la última sincronización, comparado contra el cierre semanal anterior.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay en pantalla"),
        puntos: [
          tx(
            "Qué haría ahora: las decisiones que sugieren los cambios de la semana.",
          ),
          tx(
            "Cambios por jugador: subidas y bajadas de habilidad, forma, lesiones, salario y TSI.",
          ),
          tx(
            "Intentos de transferencia detectados: puedes anotarlos, dejarlos pendientes o borrarlos si nunca llegaron a la lista.",
          ),
        ],
      },
      {
        titulo: tx("Cómo leerlo"),
        texto: [
          tx(
            "La comparación es contra el cierre semanal anterior, no contra la sincronización de hace unas horas: así una semana se lee entera y los cambios pequeños del día no tapan los importantes. Es la pantalla para abrir justo después de sincronizar.",
          ),
        ],
      },
    ],
  },
  {
    id: "alertas",
    grupo: tx("Inteligencia"),
    titulo: tx("Alertas"),
    ruta: "/insights",
    resumen: tx(
      "Reglas evaluadas en cada visita contra tu club, ordenadas por urgencia, con un buzón para archivarlas.",
    ),
    secciones: [
      {
        titulo: tx("Cómo funcionan"),
        texto: [
          tx(
            "Las alertas no se guardan: se vuelven a calcular con tus datos cada vez que abres la pantalla o el Dashboard. Cada una tiene una severidad (peligro, aviso, oportunidad o información), un título con la cifra concreta, el detalle y una acción sugerida.",
          ),
        ],
      },
      {
        titulo: tx("El buzón"),
        texto: [
          tx(
            "Una alerta se puede archivar. Al hacerlo se guarda una huella de su contenido (severidad, título, detalle y acción). Si la situación cambia, por ejemplo de «pierdes 300.000 por semana» a «pierdes 900.000», la huella deja de coincidir y la alerta vuelve sola a la lista activa: archivar no silencia un problema que empeora. Desde el buzón puedes devolver cualquier alerta archivada.",
          ),
        ],
      },
      {
        titulo: tx("Qué vigila"),
        puntos: [
          tx(
            "Plantilla: jugadores lesionados, en baja forma, envejecimiento de los de más TSI, ningún portero natural (peligro) o uno solo, concentración de nómina y jugadores caros de entrenar.",
          ),
          tx(
            "Liga: probabilidad de descenso directo, de jugar promoción, de terminar campeón, ataque o defensa por debajo de la media, favorito claro o no favorito en el próximo partido.",
          ),
          tx(
            "Partido: el clima del próximo partido, cuando cae hoy o mañana en el calendario de Hattrick.",
          ),
          tx(
            "Economía: déficit de fondo, concentración de ingresos, caja peor de lo esperado y peña de aficionados encogiendo.",
          ),
          tx("Estadio: cuándo ampliar compensaría."),
          tx(
            "Academia: juveniles a punto de perderse, promesas, y si la academia ha sido rentable o no.",
          ),
          tx(
            "Cuerpo técnico: sin médico, sin psicólogo deportivo o con los ayudantes por debajo del nivel de referencia.",
          ),
          tx("Datos: cuando tienen más de un día."),
        ],
      },
    ],
  },
  {
    id: "transparencia",
    grupo: tx("Inteligencia"),
    titulo: tx("Transparencia"),
    ruta: "/transparency",
    resumen: tx(
      "Cómo se calcula cada número, con qué constantes, de qué fuentes y hasta dónde vale.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay"),
        texto: [
          tx(
            "El catálogo de cálculos de la app. Cada ficha tiene la pregunta que responde, la fórmula, las constantes con su valor y su significado, las fuentes de cada dato, un ejemplo paso a paso, las tablas completas (matriz de posiciones, puntos de experiencia por nivel, fidelidad, entrenamiento, HTMS) y los límites.",
          ),
          tx(
            "Las constantes se leen del motor cada vez que se abre la pantalla: si un cálculo se reajusta, la página cambia sola. Es la diferencia con esta Wiki: la Wiki explica en lenguaje llano, Transparencia es la referencia exacta.",
          ),
        ],
      },
      {
        titulo: tx("Capítulos"),
        puntos: [
          tx("Qué hace cada módulo."),
          tx(
            "Entrenamiento: semanas hasta el próximo nivel, reparto del Individual, experiencia, resistencia y fidelidad.",
          ),
          tx("Posiciones y alineación: aporte por posición y once óptimo."),
          tx("Economía: balance sin transferencias."),
          tx("Pronóstico de partido, en nueve pasos."),
          tx("Liga: simulación de temporada."),
          tx("Juveniles: puntaje de selección de entrenamiento."),
          tx("Partidos: HatStats."),
          tx("HTMS y HTMS28."),
          tx("Transferencias: ROI."),
        ],
      },
    ],
  },
  {
    id: "wiki",
    grupo: tx("Inteligencia"),
    titulo: tx("Wiki"),
    ruta: "/wiki",
    resumen: tx("Esta página: la documentación de todo HT Lens."),
    secciones: [
      {
        titulo: tx("Cómo se usa"),
        texto: [
          tx(
            "El buscador filtra por cualquier palabra de los artículos, sin importar tildes ni mayúsculas, y exige que aparezcan todas las palabras escritas. El índice de la izquierda salta a cada artículo y «Abrir la pantalla» te lleva al módulo que documenta. Para las fórmulas exactas con sus constantes, Transparencia.",
          ),
        ],
      },
    ],
  },

  // ── Acerca de ────────────────────────────────────────────────────────────
  {
    id: "acerca",
    grupo: tx("Acerca de"),
    titulo: tx("Autor, Libro de visitas y Apoyar"),
    ruta: "/autor",
    resumen: tx(
      "Quién hace HT Lens, cómo pedirle funcionalidades y cómo apoyar el proyecto.",
    ),
    secciones: [
      {
        titulo: tx("Qué hay"),
        puntos: [
          tx(
            "Autor: quién hace HT Lens, sus publicaciones científicas y su divulgación.",
          ),
          tx(
            "Libro de visitas: deja un mensaje con lo que te sirve y lo que te falta. De ahí salen las funcionalidades siguientes.",
          ),
          tx(
            "Apoyar el proyecto: las formas de ayudar a que siga, explicadas con su porqué.",
          ),
        ],
      },
    ],
  },

  // ── Glosario ─────────────────────────────────────────────────────────────
  {
    id: "glosario-puestos",
    grupo: tx("Glosario"),
    titulo: tx("Puestos, formaciones y órdenes"),
    resumen: tx(
      "Cómo se nombran los puestos y cómo se describe una formación.",
    ),
    secciones: [
      {
        titulo: tx("Puestos"),
        texto: [
          tx(
            "Portero, Defensa Central, Defensa Lateral, Mediocentro, Extremo y Delantero, con los nombres de Hattrick. En sitios estrechos se abrevian DC, DL, MC, Ex y Del.",
          ),
        ],
      },
      {
        titulo: tx("Formación y reparto"),
        texto: [
          tx(
            "El nombre (4-4-2) dice cuántos juegan en defensa, medio y ataque; el extremo cuenta en la línea del medio. El reparto dice cuántos van por dentro: un 5-3-2 puede llevar tres Mediocentros, o uno y dos Extremos, y son onces distintos. Los máximos son del juego: 1 portero, 3 Defensas Centrales, 2 Defensas Laterales, 3 Mediocentros, 2 Extremos y 3 Delanteros, así que ninguna línea pasa de cinco.",
          ),
        ],
      },
      {
        titulo: tx("Órdenes individuales"),
        texto: [
          tx(
            "Normal, ofensivo, defensivo, hacia el medio y hacia la banda. Cambian cuánto aporta el jugador a cada sector: un Defensa Lateral ofensivo aporta más al ataque por su banda y menos a la defensa.",
          ),
        ],
      },
    ],
  },
  {
    id: "glosario-indices",
    grupo: tx("Glosario"),
    titulo: tx("Índices"),
    resumen: tx("TSI, HTMS, HTMS28, HatStats y rendimiento en el puesto."),
    secciones: [
      {
        titulo: "TSI",
        texto: [
          tx(
            "El índice de valor que Hattrick da a cada jugador. Crece con las habilidades y con la forma, así que un jugador en baja forma pierde TSI aunque no pierda habilidad.",
          ),
        ],
      },
      {
        titulo: "HTMS",
        texto: [
          tx(
            "El valor de las habilidades de un jugador según una tabla de la comunidad: cada nivel de cada habilidad da unos puntos y se suman las siete. La tabla no es lineal: de 16 a 17 en Defensa hay 150 puntos y de 3 a 4 hay 26, así que dos jugadores con la misma suma de niveles pueden valer cosas muy distintas. Mide lo que el jugador ya tiene, e ignora edad, forma y experiencia.",
          ),
        ],
      },
      {
        titulo: "HTMS28",
        texto: [
          tx(
            "Cuántos puntos de HTMS tendría el jugador si se le entrenara sin parar hasta los 28 años. Parte del HTMS de hoy y suma lo que rinde cada semana de entrenamiento a cada edad (16 semanas por año). Supone entrenamiento continuo, buen entrenador y un 10 % de resistencia: si tu club no es así, el número tampoco. Pasados los 28 deja de ser un potencial y pasa a ser «cuánto valía a los 28».",
          ),
        ],
      },
      {
        titulo: tx("HatStats"),
        texto: [
          tx(
            "Resume los ratings de un partido: 3 × mediocampo más las tres zonas de defensa y las tres de ataque.",
          ),
        ],
      },
      {
        titulo: tx("Rendimiento en el puesto"),
        texto: [
          tx(
            "Cuánto aporta un jugador en un puesto y orden concretos, según la tabla de contribución del Manual no Escrito, con su experiencia y fidelidad, y ajustado por forma y resistencia. Lo usan Posiciones, Alineación y Equipo.",
          ),
        ],
      },
    ],
  },
  {
    id: "glosario-jugador",
    grupo: tx("Glosario"),
    titulo: tx("El jugador"),
    resumen: tx("Niveles, especialidades y atributos que no son habilidades."),
    secciones: [
      {
        titulo: tx("Niveles de habilidad"),
        texto: [
          tx(
            "De 0 a 20: nulo, desastroso, horrible, pobre, débil, insuficiente, aceptable, bueno, excelente, formidable, destacado, brillante, magnífico, clase mundial, sobrenatural, titánico, extraterrestre, mítico, mágico, utópico y divino. Por encima de 20 se escribe divino+1, divino+2 y así.",
          ),
        ],
      },
      {
        titulo: tx("Especialidades"),
        puntos: [
          tx(
            "🎯 Técnico: precisión; mejor en ciertos eventos y lanzando penaltis.",
          ),
          tx("⚡ Rápido: velocidad."),
          tx("💪 Potente: fuerza; se crece con la lluvia."),
          tx("🎲 Imprevisible: genera eventos inesperados."),
          tx("🗿 Cabeceador: peligro de cabeza."),
          tx("🛡️ Estoico: resiste mejor las lesiones."),
          tx("🤝 Influyente: mejora a los compañeros de alrededor."),
        ],
      },
      {
        titulo: tx("Forma"),
        texto: [
          tx(
            "Sube y baja semana a semana. Entra en el rendimiento con un factor ((forma − 0,5) ÷ 7) ^ 0,45: pasar de forma baja a buena cambia mucho más que pasar de buena a excelente.",
          ),
        ],
      },
      {
        titulo: tx("Resistencia"),
        texto: [
          tx(
            "Cuánto aguanta el jugador el partido. Se entrena con la parte de resistencia del entrenamiento y tiende a un nivel de equilibrio según la edad.",
          ),
        ],
      },
      {
        titulo: tx("Experiencia"),
        texto: [
          tx(
            "Crece jugando partidos, más los importantes. Suma ln(experiencia) × 4 ÷ 3 a cada habilidad efectiva: los primeros niveles valen mucho, los últimos poco.",
          ),
        ],
      },
      {
        titulo: tx("Fidelidad"),
        texto: [
          tx(
            "Crece con el tiempo en el club y aporta hasta un nivel más en todas las habilidades de campo. Por eso vender a un jugador que lleva mucho tiempo tiene un coste que no aparece en su precio.",
          ),
        ],
      },
      {
        titulo: tx("Carácter"),
        texto: [
          tx(
            "Simpatía (de antipático a querido compañero de equipo), agresividad (de tranquilo a violento) y honradez (de infame a santito). La agresividad influye en las tarjetas.",
          ),
        ],
      },
    ],
  },
  {
    id: "glosario-competicion",
    grupo: tx("Glosario"),
    titulo: tx("Competición y análisis"),
    resumen: tx("Qué cuenta como oficial y otras palabras que usa la app."),
    secciones: [
      {
        titulo: tx("Partido oficial"),
        texto: [
          tx(
            "Liga, Promoción, Copa y Hattrick Masters. Los amistosos son reales, pero se miran aparte porque se juegan con suplentes y sin nada en juego. Torneos, duelos, escaleras y partidos de preparación no cuentan en ningún cálculo de la app.",
          ),
        ],
      },
      {
        titulo: tx("Serie"),
        texto: [
          tx(
            "Tu grupo de liga: los ocho equipos contra los que juegas la temporada. Muchas comparaciones de la app (flor de fuerza, cuello de botella, comparativa) se hacen contra la serie.",
          ),
        ],
      },
      {
        titulo: tx("Temporada y semana"),
        texto: [
          tx(
            "Una temporada de Hattrick dura 16 semanas y un año de edad de un jugador son 112 días. El calendario del juego va en hora sueca: el «hoy» de Hattrick cambia antes que el tuyo si vives al oeste de Europa.",
          ),
        ],
      },
      {
        titulo: tx("Profundidad"),
        texto: [
          tx(
            "Cuánto rendimiento pierdes en un puesto si falta el mejor titular y entra el mejor del banquillo.",
          ),
        ],
      },
      {
        titulo: tx("Cuello de botella"),
        texto: [
          tx(
            "El sector (defensa, mediocampo o ataque) donde menos ventaja le sacas al mejor rival de tu serie, o donde más pierdes si vas por detrás.",
          ),
        ],
      },
      {
        titulo: tx("Estimación, escenario y medida"),
        texto: [
          tx(
            "Una medida es un dato que dio Hattrick. Una estimación es un cálculo con margen de error (un sueldo antiguo, un pronóstico). Un escenario es una proyección que depende de supuestos (la caja sin compraventa). La app nunca presenta una estimación o un escenario como medida.",
          ),
        ],
      },
    ],
  },
];

const GRUPOS = [
  "Empezar",
  "Club",
  "Desarrollo",
  "Competición",
  "Negocio",
  "Inteligencia",
  "Acerca de",
  "Glosario",
];

/** Sin tildes ni mayúsculas, para que «posicion» encuentre «Posición». */
function normalizar(texto: string) {
  return texto.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function textoDe(a: Articulo) {
  return normalizar(
    [
      a.titulo,
      a.resumen,
      ...a.secciones.flatMap((s) => [
        s.titulo,
        ...(s.texto ?? []),
        ...(s.puntos ?? []),
        s.formula ?? "",
      ]),
    ].join(" "),
  );
}

export function WikiPage() {
  const [busqueda, setBusqueda] = useState("");
  const indice = useMemo(
    () => ARTICULOS.map((a) => ({ articulo: a, texto: textoDe(a) })),
    [],
  );
  const terminos = normalizar(busqueda).split(/\s+/).filter(Boolean);
  const visibles = indice
    .filter(({ texto }) => terminos.every((t) => texto.includes(t)))
    .map(({ articulo }) => articulo);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">{tx("Wiki")}</h1>
        <p className="text-sm text-[var(--muted)]">
          {tx(
            "Todo HT Lens explicado: qué responde cada pantalla, cómo se calcula, cómo se lee y hasta dónde vale",
          )}
        </p>
      </header>

      <input
        type="search"
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        placeholder={tx(
          "Buscar en la Wiki: cuello de botella, HTMS, ampliar estadio…",
        )}
        aria-label={tx("Buscar en la Wiki")}
        className="w-full max-w-xl rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
      />

      <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav
          aria-label={tx("Índice de la Wiki")}
          className="self-start rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm lg:sticky lg:top-4"
        >
          {GRUPOS.map((grupo) => {
            const delGrupo = visibles.filter((a) => a.grupo === grupo);
            if (delGrupo.length === 0) return null;
            return (
              <div key={grupo} className="mb-3 last:mb-0">
                <div className="mb-1 text-xs text-[var(--muted)]">{grupo}</div>
                <ul className="space-y-0.5">
                  {delGrupo.map((a) => (
                    <li key={a.id}>
                      <a
                        href={`#${a.id}`}
                        className="block rounded px-1.5 py-0.5 hover:bg-[var(--accent-soft)]"
                      >
                        {a.titulo}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="space-y-6">
          {visibles.length === 0 && (
            <p className="text-sm text-[var(--muted)]">
              {tx("Nada coincide con «")}
              {busqueda}
              {tx("». Prueba con otra palabra.")}
            </p>
          )}
          {GRUPOS.map((grupo) => {
            const delGrupo = visibles.filter((a) => a.grupo === grupo);
            if (delGrupo.length === 0) return null;
            return (
              <section key={grupo} className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--muted)]">
                  {grupo}
                </h2>
                {delGrupo.map((a) => (
                  <article
                    key={a.id}
                    id={a.id}
                    className="scroll-mt-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h3 className="text-base font-semibold">{a.titulo}</h3>
                      {a.ruta && a.ruta !== "/wiki" && (
                        <Link
                          to={a.ruta}
                          className="text-xs text-[var(--accent)] hover:underline"
                        >
                          {tx("Abrir la pantalla")}
                        </Link>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {a.resumen}
                    </p>
                    <div className="mt-4 space-y-4">
                      {a.secciones.map((s) => (
                        <div key={s.titulo}>
                          <h4 className="text-sm font-medium">{s.titulo}</h4>
                          {s.texto?.map((parrafo, i) => (
                            <p
                              key={i}
                              className="prosa mt-1 text-sm leading-relaxed"
                            >
                              {parrafo}
                            </p>
                          ))}
                          {s.puntos && (
                            <ul className="prosa mt-1 list-disc space-y-1 pl-5 text-sm leading-relaxed">
                              {s.puntos.map((punto, i) => (
                                <li key={i}>{punto}</li>
                              ))}
                            </ul>
                          )}
                          {s.formula && (
                            <pre className="mt-2 overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs leading-relaxed">
                              {s.formula}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
