# 15 — Backlog de Historias de Usuario

Producto: **Hattrick Lens**. Fuente: análisis de 53 pantallas de Hattrick Control
(`docs/14`) más las restricciones y hallazgos verificados contra la API CHPP.

Convenciones:

- **ID** `HL-nnn`, estable y citable desde código, commits y tests.
- **Prioridad** MoSCoW: Must / Should / Could / Won't.
- **Fase** F1 MVP · F2 Analytics · F3 Predicciones · F4 IA · F5 Escala.
- **Estimación** en puntos de historia (Fibonacci).
- **Estado** ✅ hecho · 🚧 en curso · ⬜ pendiente.

> **Auditoría 2026-08-01.** Este backlog había quedado desalineado con el código:
> varias historias marcadas ⬜ ya estaban implementadas. Se revisó cada ⬜ contra
> el código real (endpoints, motores, páginas del frontend, modelos de datos) y
> se corrigió el estado. Detalle de la evidencia en cada historia tocada.
>
> **Aviso de numeración.** El código ha seguido usando el prefijo `HL-nnn` en
> comentarios para funcionalidades añadidas después de este backlog, pero
> **reutilizó IDs ya asignados aquí para conceptos distintos** — por ejemplo
> `HL-099`, `HL-140`–`HL-145` y el rango `HL-15x` en el código no corresponden a
> las historias HL-099/HL-140/HL-141/HL-142 de este documento. Al buscar un
> `HL-nnn` en el código, verificar por descripción, no solo por número.

---

## Personas

**Álex, el competitivo** (60% de la base). Divisiones medias, juega para ascender.
Revisa el equipo a diario, decide entrenamiento cada semana y compra con criterio.
Quiere saber *qué hacer*, no ver más datos. Su pregunta recurrente: "¿voy bien?".

**Marta, la gestora** (25%). Piensa en el club como un negocio: caja, salarios,
amortización del estadio, valor de la plantilla. Vende antes de que caiga el valor.
Su pregunta: "¿esto es rentable?".

**Diego, el cantera** (15%). Su placer es formar jugadores desde la academia y
verlos crecer. Tolera perder mientras el proyecto avance. Su pregunta: "¿este chaval
va a llegar?".

Todas las historias se escriben desde una de estas tres personas.

---

## Definición de Preparada (DoR)

Una historia entra en sprint cuando tiene criterios de aceptación verificables, los
datos necesarios están disponibles vía CHPP (o hay decisión explícita de cómo
obtenerlos), las dependencias están cerradas y el diseño de la pantalla existe al
menos como boceto.

## Definición de Terminada (DoD)

Código tipado y con tests (dominio ≥90%, módulo ≥80%), criterios de aceptación
automatizados donde sea posible, migración reversible si toca datos, telemetría
añadida, documentación del módulo actualizada, revisado en PR y desplegado en
staging con smoke verde. **Ningún número se muestra sin que su origen esté
documentado en `docs/16`.**

---

## E1 — Conexión y sincronización

> Sin esto no hay producto. La restricción CHPP de "descarga iniciada por el usuario"
> gobierna todo el diseño de este épico.

### HL-001 · Conectar cuenta de Hattrick ✅ Must F1 · 5 pts
Como **Álex**, quiero conectar mi cuenta de Hattrick sin dar mi contraseña, para
empezar a usar la herramienta con confianza.

- Dado que no tengo cuenta conectada, cuando pulso "Conectar Hattrick", entonces se
  me redirige al servidor de Hattrick para autorizar.
- Dado que autorizo, cuando vuelvo a la aplicación, entonces mis equipos aparecen
  listados y el token queda guardado cifrado.
- Dado que Hattrick devuelve error, cuando falla el intercambio, entonces veo un
  mensaje accionable y puedo reintentar sin perder el progreso.
- En ningún momento se solicita ni almacena mi contraseña.

### HL-002 · Sincronizar bajo demanda con progreso visible ✅ Must F1 · 5 pts
Como **Álex**, quiero pulsar un botón y ver cómo se actualizan mis datos, para saber
que estoy mirando información fresca.

- El sync solo se dispara por acción del usuario, nunca por temporizador.
- Los ficheros se descargan de uno en uno, no en paralelo.
- Veo progreso por fichero y un resumen al terminar.
- Si un fichero falla, los anteriores se conservan y el sync queda como parcial.

### HL-003 · Gestionar varios equipos ⬜ Must F1 · 3 pts
Como **Álex** con equipo secundario, quiero cambiar de club desde la barra lateral
sin volver a autorizar nada.
*Auditoría: confirmado pendiente. `setActiveTeamId` solo se usa una vez, en el
callback de OAuth (`ConnectedPage.tsx`); no existe selector de equipo en
`AppLayout`.*

### HL-004 · Histórico que nunca se sobrescribe ✅ Must F1 · 8 pts
Como **Marta**, quiero que cada sincronización conserve una foto de mi club, para
poder mirar atrás cualquier semana pasada.

- Cada snapshot referencia el sync que lo produjo.
- Si nada cambió respecto al último snapshot, no se crea fila nueva.
- Ningún proceso del sistema modifica ni borra snapshots anteriores.

### HL-005 · Qué cambió desde la última vez ✅ Should F2 · 5 pts
Como **Álex**, quiero un resumen de lo que cambió desde mi último sync, para no
tener que comparar tablas a mano.
*Origen: HC "Cambios · Histórico", que muestra los datos pero no los narra.*
*Auditoría: `SyncChangesPage` + `SyncComparisonReport` + `SyncChangesFeed`
(frontend) sobre `GET /teams/{id}/sync/changes` y `/changes/history`
(`changes_history.py`, `sync_comparison.py`). Incluye panel "Qué haría ahora"
con acciones sugeridas por categoría.*

### HL-006 · Ver el dinero en mi moneda ✅ Must F1 · 3 pts
Como **Marta**, quiero que las cifras coincidan con las de Hattrick, para poder
fiarme de la herramienta.
*Origen: bug detectado — CHPP entrega moneda base; Colombia divide entre 10.*

- Todo importe mostrado está convertido por la tasa del país del equipo.
- La moneda se muestra junto a la cifra.

### HL-007 · Semana y temporada correctas ✅ **Must F1 · 3 pts**
Como **Álex**, quiero que la herramienta sepa en qué semana de Hattrick estoy, para
que los cálculos no mezclen temporadas.
*Origen: bug detectado — se tomaron partidos de la temporada 82 como si fueran de la 83.*

- La semana y temporada se leen de `worlddetails`, nunca se infieren de fechas.
- Los partidos se atribuyen a su temporada real.
- Al cambiar de temporada, los acumulados de liga se reinician.

*Auditoría: corregido en `infrastructure/chpp/parsers/__init__.py` (comentario
explícito "arregla ... el lío de temporada/jornada (HL-007)"); `world_context`
persiste semana/temporada reales (migración `0006`).*

### HL-008 · Avisar si Hattrick revoca el acceso ⬜ Should F1 · 3 pts
Como **Álex**, quiero enterarme si mi autorización dejó de funcionar, para
reconectar antes de perder datos.
*Auditoría: no hay detección proactiva. Un sync que falla por token inválido sí
se muestra en el banner de `AppLayout` (mensaje de error genérico), pero no hay
verificación periódica ni aviso explícito de "tu autorización caducó".*

---

## E2 — Plantilla y jugadores

### HL-010 · Tabla maestra de plantilla ✅ Must F1 · 8 pts
Como **Álex**, quiero ver toda mi plantilla en una tabla ordenable y filtrable, para
localizar en segundos a quien busco.
*Origen: HC "Jugadores".*

- Ordeno por cualquier columna con un clic.
- Elijo qué columnas ver y la elección se recuerda.
- Con 24 jugadores y 20 columnas la tabla responde sin salto perceptible.
- Los niveles de skill se muestran con número y color, nunca solo color.

### HL-011 · Ficha completa de jugador ✅ Must F1 · 8 pts
Como **Álex**, quiero una ficha con la historia completa de un jugador: evolución,
lesiones, tarjetas, partidos y proyección.
*Auditoría: `PlayerPage.tsx` — habilidades, 19 posiciones, momento de carrera,
entrenamiento/experiencia real, goles, radar de carácter, evolución semanal de
TSI/skills/rating por partido, comparación contra la plantilla.*

### HL-012 · Etiquetar jugadores ⬜ Should F2 · 3 pts
Como **Álex**, quiero agrupar jugadores con etiquetas propias (titulares, en venta,
proyecto) para organizarme.
*Origen: HC "Detalles" con grupos A/B/C/D fijos; nosotros con etiquetas libres.*
*Auditoría: confirmado pendiente. No hay campo de etiquetas en `models.py` ni UI.*

### HL-013 · Atributos de personalidad ✅ Should F2 · 5 pts
Como **Álex**, quiero ver carácter, agresividad, honestidad y liderazgo de mis
jugadores, para elegir capitán y anticipar tarjetas.

- Se obtienen de `playerdetails`, una llamada por jugador.
- Se refrescan como mucho una vez por semana, en segundo plano.
- Su antigüedad se indica en la interfaz.

*Auditoría: `PlayerPage.tsx` panel "Carácter" (radar agresividad/honestidad/
carácter invertido a propósito) + campo "Liderazgo"; `models.py` tiene
`leadership`/`aggressiveness`/`honesty`.*

### HL-016 · Foto de plantilla en cualquier fecha ⬜ Could F2 · 5 pts
Como **Marta**, quiero ver cómo era mi plantilla hace tres meses con sus agregados.
*Auditoría: confirmado pendiente. No hay parámetro `as_of`/fecha en el endpoint
de plantilla ni en `SquadQueryService`.*

### HL-017 · Evolución diaria de TSI y forma ✅ Should F2 · 3 pts
Como **Álex**, quiero la serie de TSI, forma y condición de un jugador con sus deltas.
*Auditoría: `PlayerPage.tsx` — gráficas de TSI y skills. Nota: agrupa por semana
ISO (`bucketWeekly`), no por día — decisión deliberada documentada en el código
para no saturar el timeline con múltiples syncs el mismo día; si se necesita
literalmente diario, hay que revisar esa función.*

### HL-018 · Lesiones actuales e históricas 🚧 Should F2 · 3 pts
Como **Álex**, quiero saber quién está lesionado, cuánto le queda y su historial.
*Auditoría: `injury_level` (CHPP `InjuryLevel`) ya codifica semanas restantes y
se muestra en `PlayerPage`, hay alerta en el dashboard y el diff de sync detecta
cambios de lesión (`sync_diff.py`). Falta un listado/historial de lesiones
dedicado por jugador — hoy solo se ve el valor actual y sus cambios sueltos en
"Cambios".*

### HL-019 · Evolución del staff ✅ Could F2 · 2 pts
Como **Marta**, quiero ver cómo cambió mi cuerpo técnico y su coste.
*Auditoría: `ClubPage.tsx` panel "Evolución del staff" sobre `staff_snapshots`
(migración `0006`).*

---

## E3 — Motor de posiciones · **el núcleo del producto**

> Este rating aparece en seis pantallas de HC. Todo lo demás cuelga de él.

### HL-020 · Calcular el rating de un jugador en cada posición ✅ **Must F1 · 13 pts**
Como **Álex**, quiero saber cuánto rinde cada jugador en cada posición y con cada
orden individual, para no colocarlos por intuición.
*Origen: HC "Posiciones", "Canteranos" y "Transferencias" — las 19 variantes.*

- Se calculan las 19 variantes: portero; defensa central normal, hacia fuera y
  ofensivo; lateral normal, hacia dentro, ofensivo y defensivo; medio normal, hacia
  fuera, ofensivo y defensivo; extremo normal, hacia dentro, ofensivo y defensivo;
  delantero normal, defensivo y hacia fuera.
- El cálculo incluye skills, forma, experiencia y especialidad.
- Es una función pura: mismos datos, mismo resultado, sin acceso a base de datos.
- El resultado se muestra con una cifra decimal, como hace Hattrick.

### HL-021 · Mejor posición en la tabla de plantilla ✅ Must F1 · 3 pts
Como **Álex**, quiero ver de un vistazo la mejor posición de cada jugador y su nota.

### HL-022 · Ranking de la plantilla por posición ✅ Must F1 · 5 pts
Como **Álex**, quiero elegir una posición y ver a todos mis jugadores ordenados por
lo que rendirían ahí.

### HL-023 · Calculadora de posiciones hipotética ⬜ Should F2 · 5 pts
Como **Álex**, quiero introducir unas skills a mano y ver el rating resultante, para
evaluar a alguien que aún no es mío.
*Origen: HC lo usa como entrada manual obligatoria; para nosotros es una utilidad
opcional porque los datos reales ya llegan por API.*
*Auditoría: confirmado pendiente. No hay endpoint de entrada manual de skills.*

### HL-024 · Calibrar el motor con mis partidos reales ⬜ Should F3 · 8 pts
Como **Álex**, quiero que las estimaciones se ajusten con los ratings que Hattrick
publicó de mis propios partidos, para que sean cada vez más exactas.
*Auditoría: confirmado pendiente para el motor de posiciones. No confundir con
el entrenamiento (`HL-031`) y la experiencia (`HL-041`), que sí se calibran
contra subidas reales — eso es otra historia, ya ✅, y se muestra en la pantalla
Motor.*

---

## E4 — Entrenamiento

### HL-030 · Ver mi configuración de entrenamiento ✅ Must F1 · 2 pts
Como **Álex**, quiero ver qué entreno, a qué intensidad, con qué entrenador y
cuántos asistentes.

### HL-031 · Semanas hasta el próximo nivel ✅ **Must F1 · 8 pts**
Como **Álex**, quiero saber cuántas semanas le faltan a cada jugador para subir la
skill que entreno, para decidir a quién mantener.
*Origen: HC "Entrenamiento actual", columna Semanas. Modelo calibrado en `docs/16`.*

- La estimación reproduce los valores observados con error menor a 0,1 semanas.
- Se muestra también la fecha estimada, no solo el número de semanas.
- Si faltan datos para estimar el sub-nivel, se indica "calibrando" en vez de
  inventar precisión.

### HL-032 · Minutos entrenados por semana ✅ Must F1 · 5 pts
Como **Álex**, quiero ver cuántos minutos jugó cada jugador en la posición que
entreno, porque de eso depende que aproveche el entrenamiento.

### HL-033 · Registro de subidas detectadas ✅ Must F1 · 5 pts
Como **Álex**, quiero un histórico de cada subida de skill con la semana y la edad
a la que ocurrió.

### HL-034 · Previsión de subidas ✅ **Should F2 · 8 pts**
Como **Álex**, quiero una lista de las próximas subidas esperadas ordenada por fecha.
*Origen: HC tiene esta pestaña **vacía**. Es nuestra oportunidad más clara.*

### HL-035 · Simulador de entrenamiento ⬜ Should F2 · 13 pts
Como **Álex**, quiero simular qué pasaría si cambio el tipo de entrenamiento, el
entrenador, los asistentes o la resistencia, para decidir con números.

- Comparo el escenario contra la situación actual lado a lado.
- Veo el efecto sobre cada jugador entrenable a N semanas.
- Veo el coste del cambio y en cuánto tiempo se recupera.
- Puedo guardar hasta tres escenarios y compararlos.

*Auditoría: confirmado pendiente tal como está descrita. Existe una
funcionalidad relacionada pero distinta en `TrainingPage.tsx` — "Entrenamiento
decidido a posteriori": elige, **después** de jugado el partido, qué tipo de
entrenamiento habría aprovechado mejor los minutos reales. Es retrospectivo y
no permite cambiar entrenador/asistentes/resistencia ni guardar escenarios
prospectivos, así que no cumple los criterios de aceptación de esta historia.*

### HL-160 · Entrenamiento decidido a posteriori ✅ Should F2 · 5 pts
Como **Álex**, quiero elegir, después de ver quién jugó y en qué posición, qué
tipo de entrenamiento habría aprovechado mejor los minutos reales — a
diferencia de HL-035 (prospectivo: simula cambios ANTES de que se jueguen los
partidos), esta es retrospectiva.
*Auditoría 2026-08-03: ya construida — panel "Entrenamiento decidido a
posteriori" en `TrainingPage.tsx`, KPI "A posteriori elegiría", ranking de
tipos de entrenamiento por exposición post-partido y tabla exportable
(`entrenamiento-a-posteriori`). Query service:
`post_match_training.py`, hook `usePostMatchTraining`. Esta historia no
tenía ID propio — solo aparecía como nota en la auditoría de HL-035 — así
que se formaliza aquí para que el backlog refleje que ya existe.*

### HL-036 · Cuánto vale entrenar ✅ **Should F2 · 8 pts**
Como **Marta**, quiero saber cuánto dinero me ha dado subir un nivel de cada skill,
medido en mis ventas reales.
*Origen: HC "Resultados por skill" con beneficio medio por nivel.*

### HL-037 · Recomendación de entrenamiento ⬜ Could F4 · 8 pts
Como **Álex**, quiero que la herramienta me diga qué entrenamiento maximiza el valor
de mi plantilla.

### HL-038 · Aviso de entrenamiento ineficiente ✅ Should F2 · 3 pts
Como **Álex**, quiero que me avise si estoy gastando plazas de entrenamiento en
jugadores mayores que tardan el doble.
*Origen: caso real detectado — Cobos (28) y Bahlek (27) tardan 11,7 y 10,8 semanas
frente a 7,5 de un jugador de 20.*
*Auditoría: `insights.py` (regla comentada "HL-038"), expuesta en `/insights` y
en la pantalla Alertas.*

### HL-039 · Curva de resistencia ⬜ Could F2 · 3 pts
Como **Álex**, quiero ver la evolución de la condición con las bandas de referencia
por edad.
*Auditoría: confirmado pendiente. No hay gráfica de condición con bandas por edad.*

---

## E5 — Experiencia

### HL-040 · Progreso de experiencia ✅ Should F2 · 5 pts
Como **Álex**, quiero ver cuánta experiencia acumula cada jugador y cuánto le falta.
*Modelo verificado: liga 1,0 · amistoso internacional 0,2 · ~26,3 por nivel.*

### HL-041 · Cuándo subirá de experiencia ✅ Could F2 · 3 pts
Como **Álex**, quiero saber en cuántos partidos subirá, para planificar convocatorias.

### HL-042 · Recomendación de capitán ✅ Could F3 · 3 pts
Como **Álex**, quiero que me sugiera el mejor capitán combinando liderazgo y
experiencia.

---

## E6 — Economía

### HL-050 · Resumen económico semanal ✅ Must F1 · 5 pts
Como **Marta**, quiero ver ingresos y gastos de esta semana y la anterior.

### HL-051 · Balance estructural sin transferencias ✅ **Must F1 · 5 pts**
Como **Marta**, quiero saber si mi club gana o pierde dinero *operando*, sin contar
compraventas, porque vender jugadores enmascara un negocio deficitario.
*Origen: HC "Balance sin Otros". Caso real: −217 k/semana pese a titular positivo.*

### HL-052 · Series económicas ✅ Should F2 · 5 pts
Como **Marta**, quiero ver la evolución de ingresos, gastos, beneficio y caja.

### HL-053 · Proyección de caja a 52 semanas ✅ **Must F2 · 13 pts**
Como **Marta**, quiero saber cuánto dinero tendré dentro de un año y con qué margen
de error.

- Con menos de cuatro semanas de histórico se usa un modelo bottom-up a partir de
  salarios, staff, estadio y patrocinio conocidos.
- A partir de ahí compiten varios modelos de series temporales y se elige el que
  mejor predice mi propio histórico mediante backtesting.
- Se muestran bandas p10/p50/p90, nunca un número solo.
- Se indica qué modelo se usó y cuál es su error histórico.

### HL-054 · Escenarios económicos ✅ Should F2 · 5 pts
Como **Marta**, quiero añadir compras y ventas planificadas y ver cómo cambia mi
caja futura.

### HL-055 · Detección de anomalías ✅ Could F3 · 3 pts
Como **Marta**, quiero que me señale semanas con movimientos atípicos.

### HL-056 · Desglose de ingresos y gastos ✅ Should F1 · 3 pts
Como **Marta**, quiero ver de dónde viene y a dónde va cada peso.

---

## E7 — Estadio

### HL-060 · Ocupación por sector ✅ Should F2 · 3 pts
Como **Marta**, quiero ver cuánto se llena cada sector de mi estadio.

### HL-061 · Detectar demanda insatisfecha ✅ **Should F2 · 5 pts**
Como **Marta**, quiero saber si estoy dejando gente fuera, porque la asistencia
observada deja de medir la demanda cuando el sector se agota.
*Caso real: tres de cuatro sectores al 100% con 91,6% de ocupación total.*

- Se marcan los sectores agotados.
- Cuando hay sectores agotados se advierte que la demanda está censurada y que las
  medias observadas subestiman la real.

### HL-062 · Modelo de asistencia ⬜ Could F3 · 8 pts
Como **Marta**, quiero predecir cuánta gente vendrá al próximo partido según clima,
rival y momento de la temporada.
*Auditoría: confirmado pendiente. `ArenaQueryService` mide ocupación observada y
demanda censurada (HL-060/061), no predice asistencia futura.*

### HL-063 · Simulador de ampliación ✅ Should F2 · 8 pts
Como **Marta**, quiero saber si ampliar el estadio se paga solo y en cuánto tiempo.

### HL-064 · Ingresos perdidos por asientos vacíos ✅ Could F2 · 2 pts
Como **Marta**, quiero ver cuánto dejo de ingresar cada partido.

---

## E8 — Partidos

### HL-070 · Sincronizar partidos ✅ Must F1 · 8 pts
Como **Álex**, quiero que mis partidos jugados entren en la herramienta.
*Auditoría: `sync_team.py` (comentario "Calendario y resultados: HL-070"),
endpoints `/teams/{id}/matches` y sync de detalle de partido.*

### HL-071 · Análisis de un partido ✅ Must F2 · 8 pts
Como **Álex**, quiero ver ratings por sector comparados con el rival, posesión,
táctica y crónica.

### HL-072 · Ocasiones clasificadas ✅ Should F2 · 5 pts
Como **Álex**, quiero ver mis ocasiones separadas por tipo: normales, eventos
especiales y contraataques.

### HL-073 · Tasas de conversión ✅ **Should F2 · 5 pts**
Como **Álex**, quiero comparar qué porcentaje de mis ocasiones acabo en gol frente
al de mis rivales, para saber si mi problema es generar o rematar.

### HL-074 · Índices agregados ✅ Could F2 · 3 pts
Como **Álex**, quiero ver HatStats y LoddarStats de cada partido.
*Auditoría: columnas HatStats/Loddar en la tabla de `MatchesPage.tsx` + KPI de
HatStats medio.*

### HL-075 · Serie histórica de ratings ✅ Should F2 · 5 pts
Como **Álex**, quiero ver cómo evolucionan mis sectores partido a partido.

### HL-076 · Rendimiento por jugador y posición ✅ Should F2 · 5 pts
Como **Álex**, quiero saber qué nota saca cada jugador en cada rol y cuál es su
mejor y peor actuación.

### HL-077 · Mejores registros 🚧 Could F2 · 2 pts
Como **Álex**, quiero ver mis mejores marcas históricas por sector.
*Auditoría: `MatchesPage.tsx` muestra un KPI "Mejor partido" (HatStats más alto),
pero es un único mejor global, no un desglose de mejores marcas por sector
(mediocampo/defensa/ataque) como pide la historia.*

---

## E9 — Liga y rivales

### HL-080 · Clasificación y calendario ✅ Must F1 · 5 pts
Como **Álex**, quiero ver la tabla de mi serie y el calendario completo.

### HL-082 · Ficha de rival ✅ Should F2 · 5 pts
Como **Álex**, quiero conocer al rival de esta jornada: su equipo, su racha y su
estado actual.

- Se muestran únicamente datos del momento presente.
- **No se almacena ni se muestra evolución histórica de equipos ajenos**, por las
  reglas CHPP sobre seguimiento de rivales.
- Los datos de rival viven en caché con caducidad, nunca en las tablas de snapshots.

*Auditoría: `RivalPage.tsx` + `rival_scouting.py` (internamente comentado como
`HL-099`, ver aviso de numeración al inicio del documento). Pide los datos del
rival en vivo en cada visita, sin persistirlos, y usa solo partidos oficiales
reales — cumple explícitamente la restricción CHPP.*

### HL-083 · Comparativa de la serie ✅ Should F2 · 5 pts
Como **Álex**, quiero comparar los ocho equipos de mi liga en TSI, salarios, edad y
experiencia.

### HL-084 · Evolución de la clasificación ⬜ Could F2 · 3 pts
Como **Álex**, quiero ver cómo ha ido cambiando el puesto de cada equipo.
*Auditoría: confirmado pendiente. `LeaguePage.tsx` muestra la clasificación
actual, no su evolución jornada a jornada.*

---

## E10 — Predicciones

### HL-090 · Simulación de temporada ✅ **Must F3 · 13 pts**
Como **Álex**, quiero saber mis probabilidades reales de ascender, ser campeón o
descender.

- Se simulan al menos 10.000 temporadas.
- Los partidos ya jugados de la temporada **en curso** entran como hechos.
- Los parámetros de cada rival llevan su incertidumbre, que se propaga a las bandas.
- El cálculo termina en menos de cinco segundos.
- Se explica en qué datos se basa y con qué limitaciones.

### HL-091 · Distribución de posiciones ✅ Must F3 · 5 pts
Como **Álex**, quiero ver la probabilidad de terminar en cada puesto, no solo el
puesto más probable.

### HL-092 · Actualización tras cada jornada ✅ Must F3 · 5 pts
Como **Álex**, quiero que mis probabilidades se recalculen cuando sincronizo
resultados nuevos.

### HL-093 · Historia de mis probabilidades ⬜ **Could F3 · 5 pts**
Como **Álex**, quiero ver cómo ha ido subiendo o bajando mi probabilidad de ascenso
a lo largo de la temporada.
*Diferencial: solo es posible porque guardamos histórico append-only. Ninguna
herramienta de Hattrick lo ofrece.*
*Auditoría: confirmado pendiente. `LeaguePage.tsx` muestra la distribución de
posición final de la simulación actual, no su evolución histórica jornada a
jornada — aunque el histórico append-only que la haría posible ya existe
(HL-004), falta el endpoint/gráfica que lo recorra.*

### HL-094 · Pronóstico del próximo partido ✅ Should F3 · 8 pts
Como **Álex**, quiero saber qué probabilidad tengo de ganar el próximo partido.

---

## E11 — Transferencias

### HL-100 · Historial de compras y ventas ✅ Should F2 · 3 pts
Como **Marta**, quiero ver qué compré, qué vendí y con qué resultado.

### HL-101 · Valoración de jugador ✅ **Must F2 · 13 pts**
Como **Marta**, quiero saber cuánto vale un jugador y en qué momento conviene
venderlo.

- Se muestra precio esperado con banda, no un número único.
- Se listan las ventas comparables en que se basa la estimación.
- Se indica la edad y fecha óptimas de venta.
- Si no hay comparables suficientes se dice claramente en vez de estimar a ciegas.

### HL-102 · Lista de seguimiento ⬜ Should F2 · 5 pts
Como **Marta**, quiero vigilar jugadores del mercado con mi precio máximo y su fecha
de cierre.
*Auditoría: confirmado pendiente. `TransfersPage.tsx` solo muestra valoración de
la propia plantilla (HL-101); no hay entidad de watchlist ni endpoint.*

### HL-103 · Alertas de cierre ⬜ Should F2 · 3 pts
Como **Marta**, quiero que me avise antes de que venza una puja que me interesa.
*Auditoría: confirmado pendiente (depende de HL-102, que tampoco existe).*

### HL-104 · Reglas de scouting ⬜ Could F3 · 8 pts
Como **Marta**, quiero definir criterios y que me avise cuando aparezca alguien que
los cumpla.
*Origen: HC "Visual Helps", que solo colorea filas.*
*Auditoría: confirmado pendiente. No hay motor de reglas configurables por el
usuario ni UI para ello.*

### HL-105 · Búsqueda en el mercado ⬜ Should F3 · 8 pts · **BLOQUEADA**
Como **Marta**, quiero buscar jugadores en el mercado con mis criterios sin salir de
la herramienta.
*Bloqueo: falta la firma completa de `transfersearch`. Verificado que el endpoint
existe y que acepta `minAge`/`maxAge`, pero hay parámetros obligatorios sin
documentación pública. Se desbloquea con la aprobación CHPP.*

### HL-106 · Pujas asistidas ⬜ Could F4 · 13 pts
Como **Marta**, quiero que la herramienta puje por mí hasta mi límite, para no tener
que estar despierta cuando vence el plazo.
*Requiere el scope `place_bid`, que Hattrick concede con autorización explícita.*

- El permiso se solicita **solo al activar la función**, nunca en el registro.
- Cada objetivo requiere confirmación previa con límite por operación.
- Existe un presupuesto máximo por semana que el sistema no puede exceder.
- Toda puja emitida queda en un registro de auditoría consultable.
- Hay un interruptor de parada inmediata siempre accesible.
- Si falla cualquier salvaguarda, el sistema no puja.

*Auditoría: confirmado pendiente — requiere el scope `place_bid`, no solicitado
en el flujo OAuth actual (`auth_chpp.py`).*

### HL-107 · Qué fue de los que vendí 🚧 **Could F3 · 5 pts**
Como **Marta**, quiero ver cómo les va hoy a los jugadores que vendí, para aprender
si vendo demasiado pronto.
*Origen: HC "ExJugadores", que lo presenta como curiosidad. Nosotros lo convertimos
en un bucle de aprendizaje sobre las propias decisiones.*
*Auditoría: el motor existe — `regret_index`/`RegretIndex` en `pricing_engine.py`
("Qué fue de los que vendiste. HL-107.") — pero no está conectado a ningún
endpoint ni a `TransfersPage.tsx`. Es lógica de dominio lista, falta cablearla.*

### HL-161 · Saldo neto por jugador ⬜ Should F3 · 13 pts
Como **Marta**, quiero saber si un jugador concreto me ha dado ganancia o
pérdida en términos absolutos, no solo su valor de mercado actual:

  − precio de compra
  − salario acumulado (semana a semana, mientras estuvo en la plantilla)
  − coste de cada vez que lo puse en el mercado
  + precio de venta
  − comisiones de la transacción
  − parte proporcional de asistentes técnicos
  − parte proporcional de personal médico

*Pedida 2026-08-03. Ingredientes que YA existen: `Player.purchase_price` y
`Player.purchased_at` (precio real de compra, de `transfersteam.xml`),
salario semana a semana en `player_snapshots` (histórico ya sincronizado),
precio real de venta vía `transfersteam.xml` (comprador/vendedor/precio por
transferencia — ver `parse_transfersteam`). Lo que NO existe todavía y hay
que decidir antes de construir:*

- *`transfersteam.xml` no trae una comisión por transacción por separado
  del precio — hay que confirmar si Hattrick cobra una comisión real
  (y su fórmula) o si "comisiones" se refiere a otra cosa.*
- *Poner un jugador en venta no tiene coste en Hattrick hasta donde se sabe
  — hay que confirmar si "costo de cada vez que lo pongo en venta" es un
  coste real de CHPP o una convención propia (p. ej. tiempo/oportunidad).*
- *Prorratear asistentes/médicos por jugador no tiene una única fórmula
  correcta: ¿reparto igual entre toda la plantilla activa esa semana?
  ¿ponderado por minutos jugados? ¿solo mientras el jugador estuvo en el
  club? Necesita una decisión de producto, no solo de ingeniería.*

---

## E12 — Juveniles

### HL-110 · Lista de juveniles ✅ Should F2 · 5 pts
Como **Diego**, quiero ver mi academia con skills actuales y máximas.

### HL-111 · Potencial estimado ✅ Should F2 · 8 pts
Como **Diego**, quiero saber hasta dónde puede llegar cada juvenil.
*HC obliga a teclear las skills a mano y a clasificar al ojo; nosotros lo tomamos de
`youthplayerlist` y lo estimamos.*

### HL-112 · Alerta de fecha límite ✅ **Should F2 · 3 pts**
Como **Diego**, quiero que me avise antes de que se me pase la fecha de promoción de
un juvenil.
*Origen: HC lo esconde en una pestaña "Límite"; debe ser una alerta.*

### HL-113 · Informes del ojeador ⬜ Could F3 · 5 pts
Como **Diego**, quiero que los comentarios del ojeador se usen para estimar el techo
de cada chaval.

### HL-114 · Rentabilidad de la academia ✅ **Could F3 · 5 pts**
Como **Diego**, quiero saber si mi academia ha sido rentable.
*Caso real: 11,24 M invertidos desde la temporada 47 y la tabla de ingresos vacía.
HC muestra ambos números y nunca los cruza.*

### HL-115 · Exposición al entrenamiento juvenil ✅ Could F3 · 5 pts
Como **Diego**, quiero saber si estoy aprovechando bien las plazas de entrenamiento.

---

## E13 — Alineación

### HL-120 · Constructor de alineación ⬜ Should F2 · 8 pts
Como **Álex**, quiero montar mi once con órdenes individuales y ver los ratings
previstos.
*Auditoría: confirmado pendiente como constructor manual. `LineupPage.tsx` solo
ofrece la mejor alineación calculada (HL-121) más selector de formación y clima
— no hay armado manual jugador-por-jugador con orden individual editable. Buena
parte del valor de producto de esta historia ya la cubre HL-121.*

### HL-121 · Mejor once posible ✅ **Should F2 · 13 pts**
Como **Álex**, quiero que me proponga la mejor alineación para una formación dada.

- Se resuelve como problema de asignación óptima, no eligiendo el mejor jugador
  posición por posición.
- Se puede excluir a lesionados, sancionados o a quien yo marque.
- Devuelve resultado en menos de un segundo para 24 jugadores.
- Explica por qué cada jugador ocupa su puesto.

*Auditoría: `lineup_optimizer.py` (algoritmo húngaro), endpoint
`/teams/{id}/lineup` (resumen "Mejor once posible (HL-121)"), `LineupPage.tsx`
con banquillo, ranking de formaciones y contribución por sector.*

### HL-122 · Optimizar contra un rival concreto ⬜ Could F3 · 8 pts
Como **Álex**, quiero la alineación que maximiza mi probabilidad de ganar *este*
partido, no una alineación en abstracto.
*Auditoría: confirmado pendiente. `lineup_optimizer.py` solo menciona HL-122 en
el docstring del módulo; no hay parámetro de rival ni ajuste táctico contra un
oponente concreto.*

### HL-123 · Ajuste por clima ✅ Could F3 · 5 pts
Como **Álex**, quiero que me avise si el clima previsto favorece o perjudica a mis
especialistas.
*Origen: HC muestra la tabla clima × especialidad como referencia estática.*
*Auditoría: endpoint `/teams/{id}/lineup/weather` (resumen "Impacto del clima
(HL-123)"), panel "Impacto del clima" en `LineupPage.tsx`.*

---

## E14 — Alertas e inteligencia

### HL-130 · Centro de alertas ✅ Should F2 · 5 pts
Como **Álex**, quiero un lugar donde estén todas las cosas que requieren mi atención.
*Auditoría: `insights.py` (docstring "HL-130"), endpoint `/teams/{id}/insights`,
`InsightsPage.tsx` con filtros por severidad y por módulo.*

### HL-131 · Resumen tras sincronizar 🚧 Should F2 · 5 pts
Como **Álex**, quiero que al terminar el sync me cuente en dos líneas qué ha pasado.
*Auditoría: el banner de `AppLayout` muestra un mensaje corto solo cuando el sync
es parcial o no hubo cambios; cuando SÍ hay cambios, el resumen narrado en
verdad vive en el panel "Qué haría ahora" de `SyncChangesPage.tsx` (HL-005), que
exige navegar a otra pantalla en vez de aparecer "al terminar el sync". La pieza
existe pero no en el momento/lugar exacto que pide la historia.*

---

## E15 — AI Assistant

> **Auditoría:** las tres historias de este épico siguen sin construirse tal
> como están descritas (no hay chat en lenguaje natural, ni un "abrir cualquier
> número" genérico, ni informe narrado). El código reutilizó los IDs
> `HL-140`/`HL-141`/`HL-142` para funcionalidades no relacionadas añadidas
> después de este backlog (diff de sync, sueldo estimado vs. real, tabla de
> Espíritu × Actitud) — ver el aviso de numeración al inicio del documento.

### HL-140 · Preguntas en lenguaje natural ⬜ Could F4 · 13 pts
Como **Álex**, quiero preguntar "¿a quién debería vender?" y recibir una respuesta
con números.

- La respuesta se construye llamando a los motores, nunca inventando cifras.
- Se muestran los datos concretos en que se basa.
- Si la pregunta no puede responderse con los datos disponibles, se dice.

### HL-141 · Cómo se calculó ⬜ Could F4 · 5 pts
Como **Álex**, quiero poder abrir cualquier número y ver de dónde sale.

### HL-142 · Informe semanal narrado ⬜ Could F4 · 8 pts
Como **Álex**, quiero recibir un resumen escrito de mi semana.

---

## E16 — Plataforma

> **Auditoría:** confirmadas pendientes las cinco. No hay medición de p95 ni
> presupuesto de rendimiento automatizado, no hay capa de suscripción/planes,
> no hay layout ni pruebas específicas de móvil, no se ha auditado
> accesibilidad (WCAG) y no existe pantalla de gestión/revocación de permisos
> CHPP (solo el flujo de conexión inicial en `auth_chpp.py`).

### HL-150 · Rendimiento ⬜ Must F1 · 8 pts
Como **Álex**, quiero que la aplicación vaya rápida siempre.
- p95 de API por debajo de 400 ms; dashboard interactivo en menos de 1,5 s.

### HL-151 · Planes y suscripción ⬜ Should F5 · 13 pts
### HL-152 · Uso desde el móvil ⬜ Should F5 · 8 pts
### HL-153 · Accesibilidad ⬜ Must F1 · 5 pts
- WCAG 2.1 AA; navegación completa por teclado; ningún dato codificado solo por color.
### HL-154 · Gestión de permisos CHPP ⬜ Must F4 · 5 pts
Como **Álex**, quiero ver y revocar en cualquier momento qué permisos le he dado a
la herramienta.

---

## Requisitos no funcionales transversales

**Cumplimiento CHPP.** Descargas iniciadas por el usuario y secuenciales. Sin
seguimiento histórico de equipos ajenos. Sin automatización no autorizada por scope
explícito. Identificación por User-Agent y aviso de copyright visible.

**Honestidad en los datos.** Ninguna estimación se presenta como certeza: toda
predicción lleva banda o intervalo. Cuando falten datos se dice, no se rellena.
Cada coeficiente del sistema tiene su origen documentado en `docs/16` y marcado como
verificado o supuesto.

**Privacidad.** Tokens cifrados en reposo. Borrado de cuenta con purga real.

---

## Resumen del backlog

*Cifras verificadas automáticamente contra el contenido de este documento.*

| Fase | Historias | Puntos | Foco |
|---|---|---|---|
| F1 MVP | 23 | 126 | Conexión, sync, plantilla, motor de posiciones, entrenamiento y economía básicos |
| F2 Analytics | 43 | 232 | Simuladores, valoración, estadio, partidos, academia |
| F3 Predicciones | 17 | 107 | Monte Carlo, scouting, calibración, optimizador contra rival |
| F4 IA | 6 | 52 | Assistant, recomendaciones, pujas asistidas |
| F5 Escala | 2 | 21 | Suscripción, móvil |
| **Total** | **91** | **538** | |

Con un equipo de dos personas y una velocidad conservadora de 20 puntos por sprint
de dos semanas, el backlog completo son unos 27 sprints. El MVP (F1) cabe en 6-7.

**Trazabilidad verificada:** 91 historias con identificador único, sin duplicados,
sin referencias huérfanas, y las 53 pantallas del inventario mapeadas a al menos una
historia. 32 historias no proceden de ninguna pantalla de HC: son mejoras propias.

**Bloqueadas:** HL-105 (firma de `transfersearch`).
**Dependencias críticas:** HL-020 bloquea HL-021, HL-022, HL-024, HL-120, HL-121,
HL-122 y HL-111. Es la primera historia que hay que cerrar después del MVP de datos.

**Estado real tras la auditoría de 2026-08-01:** 59 ✅ hechas · 4 🚧 en curso
(lógica escrita pero sin cablear o experiencia incompleta: HL-018, HL-077,
HL-107, HL-131) · 28 ⬜ pendientes de verdad. El MVP (F1) y buena parte de F2
están hechos; los únicos Must sin resolver son HL-003 (multi-equipo), HL-150
(rendimiento) y HL-153 (accesibilidad) — candidatos naturales para el próximo
sprint. Lo demás pendiente se concentra en E11 (mercado: HL-102 a HL-106), E15
(AI Assistant completo) y el resto de E16 (no-funcionales de plataforma).
