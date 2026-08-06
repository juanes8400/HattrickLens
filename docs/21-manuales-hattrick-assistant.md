# Manuales Hattrick leidos para el asistente

Fecha de lectura: 2026-07-30

Esta nota resume las reglas y manuales consultados para convertir HT Lens en un
asistente de manager. Las fuentes oficiales tienen prioridad; el Manual no
Escrito y paginas de comunidad se usan como hipotesis o conocimiento no
oficial, nunca como verdad cerrada.

## Fuentes consultadas

- Manual oficial: https://wiki.hattrick.org/wiki/Manual
- Guia para principiantes: https://user.hattrick.org/en/Help/BeginnersGuide.aspx
- Reglas en espanol: https://wiki.hattrick.org/wiki/Es/Reglas
- Entrenamiento: https://wiki.hattrick.org/wiki/Training
- Entrenamiento en espanol: https://wiki.hattrick.org/wiki/Es/Entrenamiento
- Partidos: https://wiki.hattrick.org/wiki/Match
- Balon parado: https://wiki.hattrick.org/wiki/Set_Pieces
- Entrenamiento de balon parado: https://wiki.hattrick.org/wiki/Set_pieces_training
- Academia juvenil: https://wiki.hattrick.org/wiki/Youth_Training
- Notas de entrenamiento juvenil: https://wiki.hattrick.org/wiki/Training_Notes
- Manual no Escrito: https://wiki.hattrick.org/wiki/Manual_no_Escrito
- Manual CHPP: https://wiki.hattrick.org/wiki/CHPP_Manual
- Indice XML CHPP: https://wiki.hattrick.org/wiki/CHPP_Development/
- CHPP teamDetails: https://wiki.hattrick.org/wiki/CHPP_Development/XML/teamDetails
- CHPP players: https://wiki.hattrick.org/wiki/CHPP_Development/XML/players
- CHPP playerDetails: https://wiki.hattrick.org/wiki/CHPP_Development/XML/playerDetails

## Principios para el asistente

1. La conexion CHPP es el centro del producto. No debe haber equipo ficticio si
   el usuario no ha autorizado Hattrick.
2. El asistente debe separar dato leido, inferencia y regla comunitaria. Cada
   recomendacion importante necesita etiqueta de procedencia.
3. Las descargas CHPP deben ser iniciadas por el usuario, usar solo XML y
   ejecutarse secuencialmente. No se debe escanear HTML ni automatizar acciones
   de juego como pujas, cambios de entrenador u ordenes.
4. El usuario nunca debe entregar credenciales a HT Lens. La contrasena se
   introduce solo en Hattrick durante OAuth.
5. El objetivo semanal minimo es: confirmar amistoso/copa, revisar entrenamiento
   efectivo, preparar ordenes de partido, detectar riesgos economicos y senalar
   lesionados/suspendidos.

## Modelo de partido

- El mediocampo determina la probabilidad de recibir ataques.
- Cada ataque se clasifica por sector: izquierda, centro, derecha o balon
  parado.
- El ataque del sector se compara contra la defensa rival del mismo sector.
- Jugadas pesa especialmente en mediocampistas; anotacion en delanteros; lateral
  en ataques por banda; defensa en defensas; pases apoya ataques y tacticas.
- Las ordenes individuales redistribuyen contribuciones. El asistente debe
  explicar el coste de oportunidad, por ejemplo mas defensa lateral a cambio de
  menos aporte ofensivo.
- Balon parado tiene valor propio: faltas directas/penales dependen mucho del
  lanzador y del portero rival; indirectos dependen de esfuerzo colectivo.
- Eventos especiales y especialidades agregan varianza. Deben tratarse como
  ventaja probabilistica, no como garantia.

## Entrenamiento senior

- El entrenamiento se aplica semanalmente, normalmente jueves/viernes segun
  pais.
- Un jugador recibe entrenamiento completo con 90 minutos en posicion entrenable.
  Mas de 90 minutos no agrega beneficio.
- Si jugo menos, recibe proporcion de minutos; si jugo en dos posiciones, se
  toma la que otorga mejor efecto de entrenamiento.
- Liga, copa y amistoso sirven para entrenamiento; organizar amistoso maximiza
  plazas de entreno.
- Factores principales: edad, nivel actual de habilidad, tipo de entrenamiento,
  intensidad, cuota de condicion, entrenador y asistentes.
- Los jovenes entrenan mas rapido; niveles bajos suben mas rapido que niveles
  altos; en edad alta aparece caida de habilidades.
- Set Pieces entrena a todos los que juegan, con bonus para lanzador y portero.

## Academia juvenil

- Juveniles entrenan con entrenamiento primario y secundario; el primario pesa
  mas.
- La academia revela habilidades mediante reportes del entrenador/scout.
- Para revelar datos, el jugador debe jugar minutos en posiciones relevantes.
- Un juvenil puede promocionar si tiene al menos 17 anos y lleva una temporada
  en la academia.
- El asistente debe buscar talentos con potencial oculto, recomendar posiciones
  para revelar skills y evitar entrenar una habilidad ya capada.

## CHPP y datos necesarios

Para que el asistente sea util desde el primer sync, priorizar:

- `teamdetails`: identidad del usuario, equipos, liga, serie, copa y amistoso.
- `players` y `playerDetails`: plantilla, skills, forma, experiencia,
  especialidad, lesiones, tarjetas, salario y TSI.
- `training`: tipo, intensidad, cuota de condicion y ultimo entrenamiento.
- `trainingevents`: subidas confirmadas para calibrar predicciones.
- `club` y `stafflist`: entrenador, asistentes, espiritu/confianza y staff.
- `matches`, `matchdetails`, `matchlineup`: historial, ratings, ocasiones,
  tacticas, ordenes y desempeno por sector.
- `economy` y `arenadetails`: caja, flujo semanal y estadio.
- `worlddetails`: fechas de proxima actualizacion y entrenamiento por liga.

## Funciones que deben salir de esta lectura

- Asistente de conexion: detectar si falta autorizacion, explicar OAuth y guiar
  al usuario al boton correcto.
- Checklist semanal: amistoso, entrenamiento, ordenes, lesionados, tarjetas,
  economia y proximo rival.
- Entrenador de entrenamiento: quien recibio 90/90, quien desperdicia minutos,
  semanas estimadas a pop y ROI esperado.
- Analista de partido: comparar mediocampo, defensa/ataque por sector, balon
  parado, especialidades y tacticas probables.
- Asistente de cantera: plan de revelado por posicion, prioridad de entreno y
  fecha minima de promocion.
- Modo honestidad: cada consejo debe indicar si se basa en CHPP leido, manual
  oficial o conocimiento comunitario trazable.

## Lectura especifica del Manual no Escrito

Fuente: https://wiki.hattrick.org/wiki/Manual_no_Escrito

Estado de confianza: comunidad. Para posiciones y órdenes individuales es la
fuente operativa declarada del producto; no se sustituye por ajustes contra
estrellas. No se presenta como regla oficial, sino como investigación
comunitaria trazable a su matriz y fórmulas publicadas.

### Habilidades, TSI y rendimiento

- El TSI no debe usarse solo para decidir posiciones. El asistente debe mirar
  skills, forma, condicion, experiencia, especialidad, lealtad y salud.
- La forma afecta fuerte el rendimiento. El Manual no Escrito propone una curva
  de factor forma; esto encaja con un asistente que explique por que un jugador
  con mas skill puede rendir peor si llega bajo de forma.
- La condicion baja rendimiento a medida que avanza el partido; si se usa
  Presionar, la caida se acelera. El asistente debe revisar stamina antes de
  recomendar presion o prorroga.
- La experiencia aporta a las habilidades efectivas y se acumula por minutos,
  con distinta ganancia segun tipo de partido. Debe incorporarse en el modulo
  de capitan, penales, partidos decisivos y desarrollo.
- Lesion/bruised no es binario: un jugador tocado puede rendir cerca de un
  porcentaje de salud, pero alinear lesionados aumenta riesgo. El asistente debe
  advertirlo como riesgo, no solo como disponibilidad.

### Aportes por posicion y orden individual

- El Manual no Escrito lista matrices de contribucion por puesto. El Motor de
  Posiciones usa esas matrices directamente para explicar tradeoffs de
  alineacion:
  - arquero aporta a defensa central y lateral, y su defensa secundaria tambien
    cuenta;
  - defensas ofensivos sacrifican defensa por mediocampo;
  - defensas hacia lateral mueven defensa al costado y aportan algo a ataque
    lateral;
  - laterales ofensivos suben ataque lateral con coste defensivo;
  - mediocampistas ofensivos/defensivos/hacia lateral redistribuyen pases,
    defensa, lateral y jugadas;
  - delanteros hacia lateral concentran ataque en banda; delanteros defensivos
    aportan mediocampo y pases, especialmente si son tecnicos.
- Acción de producto: el optimizador de alineación debe mostrar "lo que gano" y
  "lo que pago" por cada orden individual, no solo un índice final.

### Motor de partido y probabilidades

- El documento refuerza la lectura de partido por ratings de equipo, no por
  estrellas individuales.
- Distribucion comunitaria de ocasiones regulares: centro 35%, cada banda 25%,
  tiros libres 15%. Usar como aproximacion para explicar el plan ofensivo.
- Se mencionan 15 eventos normales aproximados: exclusivos de cada equipo y
  abiertos. El mediocampo influye en cuantos eventos llegan.
- Ataque contra defensa se modela con una curva no lineal. El asistente puede
  usarla como estimador probabilístico, siempre etiquetado como "modelo
  comunitario".
- La localia, PIC, Normal, MOTS y CA modifican el mediocampo efectivo. El
  asistente debe explicar el impacto de actitud sobre posesion esperada.

### Tacticas

- Contraataque: depende de defensa y pases de defensores, con penalizacion al
  mediocampo. Debe recomendarse cuando el rival supera en mediocampo y nuestra
  defensa puede absorber ataques.
- Tiros lejanos: depende del promedio de anotacion y pelota parada de jugadores
  de campo, con penalidad a mediocampo y ataque. Debe sugerirse solo si el
  plantel realmente tiene ese perfil.
- Atacar por bandas / por el centro: el nivel tactico se aproxima con la suma de
  pases de los jugadores de campo. El asistente debe revisar si la conversion de
  chances compensa debilitar otros sectores.
- Presionar: su nivel cae durante el partido por condicion. El asistente debe
  advertir si el plan depende de resistencia insuficiente.
- Marca personal: afecta habilidades del marcador y marcado, no pelota parada
  ni arquero. Debe usarse con cuidado y con skills efectivas, no crudas.

### Psicologia, TS y gestion de temporada

- PIC sube espiritu y baja mediocampo inmediato; MOTS sube mediocampo inmediato
  y golpea el espiritu. El asistente debe pensar en horizonte de varias semanas,
  no solo el proximo partido.
- Reducir intensidad puede subir espiritu, pero castiga forma/entrenamiento. El
  asistente debe tratarlo como maniobra excepcional.
- Sobreconfianza afecta mediocampo; experiencia negativa/desorganizacion puede
  afectar ratings. El modulo de previa debe revisar riesgo de overconfidence,
  formacion y capitan.
- Vender jugadores puede bajar TS y experiencia de formacion si eran regulares.
  El asistente de transferencias debe advertir impacto deportivo invisible.

### Entrenamiento y juveniles

- Entrenamiento efectivo estimado: intensidad menos cuota de condicion. Cruzar
  con `training.TrainingLevel` y `StaminaTrainingPart`.
- Efectos por posicion: 100%, parcial y osmosis. Mantenerlos configurables y
  mostrar procedencia.
- Pelota parada entrena a todos los que juegan, con bonus de 25% para arquero y
  lanzador.
- Condicion tambien depende de minutos: 0 minutos aun recibe parte de condicion;
  90 minutos recibe el maximo.
- En juveniles, primario/secundario diferentes ayudan a revelar mas informacion.
  Entrenamiento individual depende de la posicion con mas minutos.

### Como convertirlo en asistente

- Cada recomendacion avanzada debe exponer una etiqueta:
  `CHPP`, `Manual oficial`, `Manual no Escrito`, `Observado en tu club` o
  `Supuesto`.
- Donde el Manual no Escrito da formulas, HT Lens debe guardarlas como
  parametros calibrables, no como constantes sagradas.
- Las pantallas clave a construir con esta lectura:
  - "Por que esta alineacion": contribuciones y tradeoffs por sector.
  - "Plan de partido": posesion esperada, sectores vulnerables, tactica viable,
    riesgo de stamina y TS.
  - "Plan de temporada": PIC/MOTS, caja, entrenamiento, ventas y copa.
  - "Juveniles": que posicion usar para revelar cada skill y cuando promocionar.
