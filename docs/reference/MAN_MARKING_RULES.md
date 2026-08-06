# Marcaje individual (orden de marcaje al hombre) — reglas reales de Hattrick

Fuente: reglas oficiales del juego, pegadas por el usuario el 2026-08-02.
Referencia para `backend/app/domain/engines/rival_scouting.py::suggest_man_marking`.

## Texto original

Con el marcaje individual, ordenas a uno de tus jugadores que persiga y
neutralice a un jugador clave del otro equipo. Marcar al hombre nunca está
libre de riesgos, así que úsalo con precaución. Aunque el jugador correcto
en el momento correcto puede ser una forma muy eficiente de inclinar un
partido a tu favor.

El principio consiste en que ordenas a uno de tus jugadores convertirse en
la sombra de un jugador concreto de tu rival u obstaculizar su juego. Si el
jugador oponente está en el campo, esta orden se activa a los cinco minutos
de que se den las circunstancias para que empiece el marcaje y en ese
momento tu jugador contribuirá mucho menos de lo normal. En concreto, tu
jugador contribuirá un 50% menos si el jugador a marcar está cerca y un 65%
menos si está lejos de él. El beneficio de esto es que la contribución del
jugador marcado también descenderá. Cuánto descienda dependerá de lo
eficiente que sea tu jugador en el marcaje. La clave está, por supuesto, en
saber cuándo merece la pena ordenar este marcaje y cuándo es mejor evitarlo.

Un jugador con orden de marcar individualmente no puede tener otras
instrucciones: esto significa que esta orden cancela cualquier otra que
haya recibido anteriormente como jugar ofensivo, defensivo, hacia medio o
hacia lateral.

Solo puedes ordenar un marcaje individual por partido a cualquiera de tus
centrales, laterales o centrocampistas y solo podrás realizarlo sobre un
delantero, extremo o centrocampista contrario. Si el jugador a marcar no
está alineado o juega en una posición no susceptible de marcaje, la orden
se anula, aunque tu jugador seguirá sufriendo la penalización del 10% de su
contribución. No obstante, aunque una orden no empiece activa al inicio del
partido, puede activarse durante el transcurso del mismo, si el jugador a
marcar entra como sustituto o si empieza a jugar en una posición en la que
pueda ser marcado.

Mientras las orden de marcaje individual esté activada, un jugador no
contribuirá con sus habilidades al nivel de táctica del equipo (como
Presionar o Contraataques). Por otro lado, contribuirá a este nivel de
táctica si la orden no está activa, siendo la penalización del 10%
mencionada anteriormente la única que se tenga en cuenta.

Defensa es la habilidad que más importa para el jugador que realiza el
marcaje. Se compara con la habilidad más alta del jugador objeto del
marcaje. Esto marca lo grande que será la disminución en la contribución
del jugador marcado. Los jugadores Potentes o sin especialidad, obtendrán
un 10% o un 5%, respectivamente, de bonificación en su habilidad de Defensa
para este cálculo. Por otro lado, si el jugador marcado tiene la
especialidad de Técnico, perderá un 8% de su habilidad más alta durante el
marcaje al hombre, pero si su especialidad es Imprevisible, ganará un 8% en
ella. La forma, la resistencia, la fidelidad o la bonificación por club de
origen y la salud también influyen tanto para unos como para otros. Ten en
cuenta que todas estas bonificaciones y penalizaciones solo se tienen en
cuenta para el cálculo del marcaje al hombre y no se tienen en cuenta para
las calificaciones.

Cualquier penalización para el marcador afecta a todas las habilidades,
excepto portería y balón parado. Las penalizaciones sobre el jugador
marcado excluyen, además de lo anterior, Defensa.

## Puntos clave para el motor (`suggest_man_marking`)

1. **Quién puede marcar**: defensa central, lateral o centrocampista
   (interior). **A quién se puede marcar**: delantero, extremo o
   centrocampista (interior) rival. Cualquier combinación de esas dos
   listas es una orden LEGAL — no solo la diagonal "eficiente".
2. **Cerca (-50%) vs. lejos (-65%)**: la tabla del Manual no Escrito
   (lateral↔extremo, defensa central↔delantero, interior↔interior) es la
   combinación "cerca" — la más eficiente, -50% para el marcado. Cualquier
   otra combinación válida de la lista 1 es "lejos": -65%, sigue siendo
   legal pero menos eficiente. El motor actual solo sugiere combinaciones
   "cerca"; cuando no hay ninguna disponible, puede valer la pena sugerir
   una "lejos" en vez de no sugerir nada, dejando claro que es la opción
   subóptima.
3. **Solo una orden de marcaje por partido**, y cancela cualquier otra
   instrucción individual que tuviera el marcador (ofensivo/defensivo/hacia
   medio/hacia lateral).
4. **Riesgo de objetivo equivocado**: si el objetivo no está en el campo o
   juega una posición no marcable, la orden se anula PERO el marcador igual
   pierde un 10% fijo de su contribución. Esto es un riesgo real de dar la
   orden con una alineación rival que aún no se confirmó.
5. **Costo de oportunidad**: mientras la orden está activa, el marcador NO
   contribuye al nivel de táctica de equipo (Presionar, Contraataques...).
   Sin la orden activa, sí contribuye (con la única penalización del 10%
   normal de cualquier jugador con instrucción individual).
6. **Cómo se calcula la magnitud real** (no replicable con datos de CHPP de
   un rival — sus skills exactas están ocultas): Defensa del marcador vs.
   la habilidad más alta del marcado, con modificadores por especialidad
   (Potente +10% Defensa, sin especialidad +5% Defensa, Técnico -8% a su
   habilidad más alta, Imprevisible +8%), forma, resistencia, fidelidad,
   bonus de club de origen y salud de ambos jugadores. La penalización al
   marcador afecta todas las skills menos portería y balón parado; al
   marcado, todas menos esas dos y además Defensa.

## Qué puede y no puede saber HT Lens de esto para un rival

- El marcador (nuestro jugador): TODO se conoce — Defensa real, forma,
  resistencia, especialidad, etc.
- El marcado (jugador rival): solo TSI y, si apareció en un partido ya
  jugado, nombre y posición (`matchlineup.xml`). Su Defensa/habilidad más
  alta real, especialidad, forma y demás modificadores están ocultos por
  CHPP. Por eso el motor usa TSI como única señal de peligrosidad, y por
  eso NUNCA se calcula una magnitud de penalización real — solo se declara
  la confianza como aproximada.
