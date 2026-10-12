# Los criterios del Comparador de Transferencias de Hattrick

**Fecha del sondeo:** 2026-10-10
**Estado de la evidencia:** derivado del propio juego, preguntándoselo
**Validación:** 84 casos fijados en `backend/tests/test_criterios_hattrick.py`,
de los cuales **33 se predijeron a ciegas** —la regla escrita primero, la
consulta después— en tres tandas separadas de perfiles nunca vistos, y acertó
los 33. La primera vez que se hizo esa prueba acertaba 8 de 15.

## Qué es esto

Cuando le das al botón **Comparar traspasos** de un jugador, Hattrick decide con
qué criterios va a buscar ventas parecidas y te los enseña. Este documento
recoge **la regla que hay detrás de esa decisión**, reproducida en
[`criterios_hattrick.py`](../../backend/app/domain/engines/criterios_hattrick.py).

No está publicada en ningún sitio. La única explicación oficial que existe es un
post de **flameron (HT) del 29 de enero de 2009** en el foro Global, archivado en
[HTs on Global/Transfer compare](https://wiki.hattrick.org/wiki/HTs_on_Global/Transfer_compare),
y lleva diecisiete años sin tocarse. El [historial oficial](https://www.hattrick.org/en/Help/History.aspx)
reconoce que el comparador se actualizó en la **temporada 69 (30 de julio de
2018)** sin decir qué cambió, y el sondeo confirma que al menos una cosa cambió:
en 2009 decían que la tercera habilidad va *siempre* en rango, y hoy puede ir
clavada.

## Cómo se obtuvo

La pantalla de comparación tiene un panel **«Editar búsqueda»** que acepta un
perfil cualquiera --edad y las siete habilidades, exista ese jugador o no-- y
devuelve los criterios que Hattrick calcula para él. Es una máquina a la que se
le puede preguntar.

Se le hicieron **unas 880 consultas** con perfiles sintéticos --520 el
2026-10-10 y 360 más el 2026-10-11--, moviendo un eje cada vez y buscando las
fronteras por bisección. Los datos en bruto, consulta a consulta, están en
[`sondeo-comparador/`](sondeo-comparador/).

Tres comprobaciones de control, antes de nada:

- **La ficha desde la que se abre el panel no influye.** El mismo perfil
  inventado, enviado desde la ficha de un portero y desde la de un defensa,
  devuelve criterios idénticos.
- **Hattrick recalcula de verdad.** Cambiar una sola habilidad cambia los
  criterios; el panel no se limita a reenviar lo que le metes.
- **El panel añade un criterio que la página normal no tiene.** Al editar
  habilidades aparece `Especialidad = ‹la del jugador base›`, y la página sin
  editar no lo lleva: se comprobó en cinco fichas distintas. Es un artefacto
  del panel, se descarta en los sondeos y **no va al producto**.

Esto cumple [`AGENTS.md`](../../AGENTS.md): la regla no se ajustó contra la
plantilla del propietario, se le preguntó al juego, que es la fuente general que
esa norma exige. Los perfiles sondeados son inventados.

## La regla

### 1. El tipo de jugador

Lo decide **la habilidad más alta**, con dos excepciones.

**Hattrick no tiene puesto de pasador.** Si lo que más tiene es Pases, el tipo
lo da la mejor de las demás. Un Pases 15 con Jugadas 12 se trata como
mediocentro.

**La Portería le gana a la Defensa desde cuatro niveles más abajo.** Con
Defensa 16 y Portería 12, Hattrick saca criterios de portero. Se bisectó la
frontera para cada Defensa de 1 a 20:

| Defensa | 1–3 | 4–7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Portería mínima | — | 4 | 5 | 6 | 7 | 8 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |

Es `max(4, Defensa − 3)` hasta Defensa 11 y `Defensa − 4` desde 12. Hace falta
un 4 de Portería como mínimo: con Defensa 3 y Portería 3 sale defensa. No lo
mueve ninguna otra habilidad --ni el balón parado-- y sí se aplica a una
Defensa que ganó el reinado por la reclasificación del pasador. **El escalón
en Defensa 12 está medido, no explicado.** Es la única excepción a «manda la
más alta»: se comprobaron las treinta parejas con una a 16 y otra a 13.

A igualdad de nivel el orden es
**Lateral › Anotación › Defensa › Jugadas › Portería › Pases**.

La primera medición puso la Portería tercera, y era falso: salía de que con
todo a 12 gana el portero y de que con Portería 11 y Defensa 11 también, dos
casos que el sesgo de arriba explica. Medido empate a empate, con Jugadas 10 y
Portería 10 sale mediocentro.

### 2. La plantilla de cada tipo

Cada tipo mira seis habilidades, en este orden:

| domina | 1º | 2º | 3º | 4º | 5º | 6º |
|---|---|---|---|---|---|---|
| Portería | Portería | Defensa | **Balón parado** | Lateral | Anotación | Jugadas |
| Defensa | Defensa | Pases | Jugadas | Lateral | Anotación | Portería |
| Jugadas | Jugadas | Pases | Defensa | Lateral | Anotación | Portería |
| Lateral | Lateral | Jugadas | Pases | Defensa | Anotación | Portería |
| Anotación | Anotación | Pases | Lateral | Jugadas | Defensa | Portería |

### 2b. Y no todas pueden ser criterio

De las seis que mira cada tipo, **unas pueden ser criterio y otras sólo reciben
tope**, valgan lo que valgan:

| domina | puede ser criterio | **nunca** |
|---|---|---|
| Portería | Defensa, Balón parado | Jugadas, Lateral, Anotación |
| Defensa | Pases, Jugadas, Lateral | **Anotación**, Portería |
| Jugadas | Defensa, Lateral, Pases, Anotación | Portería |
| Lateral | Jugadas, Pases, Anotación, Defensa* | Portería |
| Anotación | Jugadas, Lateral, Pases | Portería, **Defensa** |

A un central no se le compara por Anotación ni con un 9; a un extremo sí, ya
con un 5. **A nadie de campo se le compara por Portería.** El asterisco del
extremo es la exclusión condicional de más abajo. Es la lista de *«secondary, tertiary and quartile skills chosen by
player type»* que el post de 2009 decía que existía sin decir cuál era.

La Portería del defensa se barrió de 5 a 13 con Defensa 18 y de 5 a 7 con
Defensa 12: sólo le sube el techo. La primera medición la daba como elegible y
era falso --con eso, a un defensa con algo de Portería se le clavaba
«Portería = X» como *segundo* criterio, que es lo peor que podía pasar aquí
porque el segundo criterio sí se manda a buscar--.

**Y lo que no puede ser criterio tampoco cuenta para la rareza.** Un central de
Defensa 12, Pases 10 y Anotación 9 sigue saliendo ajustado: a Hattrick un
central goleador no le parece un jugador más raro, le parece el mismo central.

El portero es el único que mira **balón parado**. En un jugador de campo no
influye en nada: con Defensa 14 y Jugadas 10, un balón parado de 0, de 12 o de
20 da exactamente los mismos criterios.

**Y hay una exclusión más que depende del nivel: al extremo, la Defensa no le
es criterio si no llega al nivel de la Anotación.**

| perfil | Defensa |
|---|---|
| Lateral 18, Anotación 12, Defensa 7 a 11 | sólo le sube el techo |
| Lateral 18, Anotación 12, Defensa 12 | entra, y la Anotación le cede el segundo puesto |
| Lateral 18, Anotación 9, Defensa 5 a 8 | sólo le sube el techo |
| Lateral 18, Anotación 9, Defensa 9 | entra |

**No es simétrico**: con la Defensa arriba, la Anotación entra siempre --con
Lateral 18 y Defensa 12 entra con 9, 10, 11 y 12--. Y **no es general**: al
mediocentro no le pasa (con Jugadas 18 y Anotación 12, una Defensa 9 sí es
criterio) ni al defensa con su Lateral. Es del extremo y de esa pareja.

Esto explica cuatro de los seis contraejemplos que habían quedado sin
explicación en el orden de criterios, y sube los tres filtros de
`transfersearch` a 60 de 60 en los perfiles plausibles.

### 3. El orden de los criterios

Se ordenan por **`nivel − posición en la plantilla`**, de mayor a menor. Eso
significa que **adelantar cuesta tantos niveles como puestos haya que subir**:
con Pases en 7, Jugadas --que va justo detrás-- adelanta con 8, pero Lateral
--dos puestos más atrás-- necesita 9.

Es la regla que flameron describía en 2009 sin dar el número.

**Pero esto es un ajuste, no la regla de Hattrick, y está demostrado que no lo
es.** El 2026-10-11 se enumeraron los quince subconjuntos de un extremo con
Lateral 16 y las demás a 9, y salió esto:

| perfil | orden |
|---|---|
| Pases 9, Anotación 9 | Lateral, **Pases, Anotación** |
| Pases 9, Anotación 9, Defensa 9 | Lateral, **Anotación, Pases**, Defensa |

Las mismas dos habilidades, los mismos niveles, y meter una tercera les da la
vuelta al orden entre sí. Eso descarta a la vez cualquier orden por clave
--añadir un elemento no puede permutar a otros dos--, una lista de prioridad
por puesto y una asignación a huecos. El mediocentro tiene la misma
contradicción: con Pases 10 y Anotación 11 manda la Anotación, lo que exige
que pese 2; con Pases 7, Defensa 9 y Anotación 8 mandan los Pases sobre la
Anotación, lo que exige que pese 3.

Lo que tenemos clava los 146 casos fijados, las 24 fichas reales incluidas, y
falla en una familia sintética --tres secundarias juntas entre 7 y 9, alguna a
cero-- que está medida entera en `sondeo-comparador/fase-a.txt`, FASE Q. Se
usa porque es lo mejor que hay, no porque sea el mecanismo.

**La habilidad que da el tipo va siempre la primera**, aunque otra tenga más
nivel. Por eso un Pases 16 con todo lo demás a cero empieza por
`Lateral = nulo`: clavar el Lateral es lo que separa a un pasador de un extremo.

### 4. Qué operador le toca a cada puesto

| puesto | regla |
|---|---|
| **1º** | siempre **exacto** |
| **2º** | **techo** por debajo de 3 (2 en el portero) · **exacto** hasta 9 (6 en el portero) · **banda `[v−1, v+1]`** desde 10 (7 en el portero) |
| **3º** | cae a techo por debajo de 5 · **banda** de 5 a 10 · **suelo `≥ v`** desde 11 |
| **4º** | sólo existe si llega a 5. Banda estrecha como el 3º por debajo de 8, y ancha `[v−2, v+3]` de 8 en adelante, **cortada arriba por el nivel de la 1ª**: con Defensa 9 y las otras tres a 8 sale `Lat 6-9`, y subiendo sólo la Defensa a 10 sale `Lat 6-10`. Un cuarto puesto no puede pedir más de lo mejor que tiene el jugador |
| **resto** | **techo** |

La banda del 3º mide `[v−1, v+1]` con la búsqueda ajustada y `[v−1, v+2]` con la
búsqueda holgada.

**La segunda se abre a banda antes de tiempo** si la tercera llega a 7, si hay
una cuarta que llegue a 5, o si empata con la primera. Lo decía 2009: *«lo mismo
ocurre si la tercera es alta»*; el umbral son siete, y eso no lo decía.

**El balón parado del portero** va aparte: techo por debajo de 5, banda
`[v−2, v+2]` ajustada o `[v−3, v+3]` holgada hasta 15, y de 16 en adelante un
suelo fijo en 14 que ya no depende del nivel.

### 5. El dial

Hattrick afloja **toda la búsqueda a la vez** cuando el jugador es raro: la
edad, la anchura de la banda del tercero y los techos. Es el equilibrio que
declararon en 2009 entre precisión y resultados suficientes.

```
rareza = v1 + v2 + max(0, v3 − 6) + max(0, v4 − 6)
         (sólo las cuatro primeras de su plantilla, ordenadas de mayor a menor;
          el balón parado del portero descuenta 10 en vez de 6)

holgado  ⟺  rareza ≥ umbral   o   v1 ≥ 17
```

| tipo | umbral |
|---|---|
| Portería | 21 |
| Defensa | 25 |
| Jugadas, Lateral, Pases, Anotación | 27 |

**Un cuarto criterio de identidad baja el listón un punto**: un jugador con
cuatro habilidades de verdad encaja en menos moldes que uno con tres. Medido
con un delantero de Anotación 11, Pases 10, Lateral 9 y Jugadas 8 --rareza
26-- que afloja, cuando el mismo tipo con sólo dos habilidades aguantaba
hasta 27.

**Y con las dos primeras habilidades empatadas el umbral baja a 25**, sea el tipo
que sea. Un extremo con Lateral y Anotación a 12 y Pases 7 --rareza 25-- afloja,
mientras que el mismo extremo con la segunda por debajo aguantaba hasta 27. Un
jugador con dos habilidades iguales arriba encaja en menos moldes.

**Hasta los 21 años no hay dial que valga**: al jugador joven le aprietan toda
la búsqueda. El mismo perfil --Defensa 17, Jugadas 3-- sale ajustado a los 19,
20 y 21, y holgado a los 22 y a los 25. Y aguanta hasta con un perfil de élite:
un Defensa 19 con Jugadas 15 sigue ajustado a los 20.

Los techos de las habilidades sobrantes son 4 con la búsqueda ajustada y 5 con
la holgada mientras el jugador tenga menos de 5 en esa habilidad; de 5 en
adelante siguen al nivel: **`v+1` ajustado y `v+2` holgado**. Barrido entero en
los dos modos.

### 6. La edad

```
hasta 21  ->  clavada
22 a 31   ->  clavada si ajustado, ±1 si holgado
32 a 34   ->  ±1 SIEMPRE, aunque el resto siga ajustada
35 y más  ->  «>= 35», un suelo sin tope, si la búsqueda va ajustada
```

**Al PASADOR no se le abre a los 32**: a quien lo más alto que tiene son Pases
la edad le aguanta clavada hasta los 34. Dándole la vuelta al mismo par de
habilidades cambia el resultado --Pases 13 y Jugadas 7 da `= 33`, y Jugadas 13
con Pases 7 da `32-34`--. Es la misma excepción que le fuerza el primer
criterio, asomando por otro sitio.

**A los 17, y sólo a los 17**, aparece además un tope de días (`Días <= 24`).
El número es **fijo**: se pidió el mismo perfil de 17 años desde la ficha de un
jugador de 2 días y desde la de uno de 20, y las dos veces salió 24.

## Lo que NO se compara

Forma, resistencia, especialidad, experiencia, liderazgo, carácter,
nacionalidad, TSI, y el balón parado de los jugadores de campo. Coincide con lo
que declararon en 2009, y con lo que HT Lens ya excluía.

## Cuánto se le cree

Las **75 pruebas** de `test_criterios_hattrick.py` fijan otros tantos casos
contra lo que contestó Hattrick, no contra el módulo. De ellos, **27 se
predijeron a ciegas** --la regla escrita primero, la consulta después-- en dos
tandas separadas de 15 y 12 perfiles que el modelo no había visto, y acertó
los 27.

La primera vez que se hizo esa prueba, el modelo acertaba 8 de 15. Cada fallo
está anotado en los datos crudos junto a la regla que lo arregló, porque saber
por dónde falló importa tanto como la regla.

## Lo que queda desconocido

- **El MECANISMO del orden de los criterios.** No es un orden por peso de
  habilidad: está demostrado arriba con un contraejemplo de dos filas. Lo que
  hay es un ajuste que acierta todo lo medido salvo una familia sintética, y
  se sabe exactamente cuál. Afecta al orden de la lista y, por tanto, **a qué
  tres habilidades le pedimos a `transfersearch`**, que acepta sólo tres.
- **Por qué el escalón del sesgo del portero está en Defensa 12.** La tabla
  entera está medida de 1 a 20; el motivo, no. Por encima de 20 no se sondeó.
- **Cuándo entra el TERCER criterio en general.** El caso del mediocentro ya
  está medido y escrito --su Lateral entra con 7, o con 5 si la Anotación llega
  a 5 y la Defensa no pasa de 4--, pero no se sabe si los demás tipos tienen
  condiciones parecidas en otras habilidades. Lo no medido usa 5.
- **La entrada y el techo del CUARTO criterio.** Con Anotación 10, Pases 8 y
  Lateral 6, una Jugadas 5 recibe techo donde el modelo le pone banda; y con
  Lateral 16, Pases 11, Anotación 11 y Jugadas 9, el techo de la banda sale un
  nivel más bajo de lo que el modelo calcula. Dos de sesenta, ninguno cambia la
  búsqueda.

## El listón del dial va por PAREJA, no por tipo

Se medía con una sola segunda habilidad por tipo, y de ahí salió un listón por
tipo. Es falso en cuatro de doce parejas barridas:

| domina (16) | segunda | afloja en rareza |
|---|---|---|
| Defensa | Pases, Jugadas o Lateral 9 | 25 |
| Jugadas | Pases 11 | 27 |
| Jugadas | Defensa 10 | 26 |
| Jugadas | Lateral 9, Anotación 9 | 25 |
| Lateral | Pases 11 | 27 |
| Anotación | Pases 11, Jugadas 11 | 27 |
| Anotación | Lateral 9 | 25 |
| Portería | Defensa 5 | 21 |

Se lee como una **prima de rareza de la pareja**: las naturales --el
mediocentro que pasa, el extremo que pasa, el delantero que pasa-- piden 27, y
las raras aflojan antes. El *por qué* no se sabe, y con doce celdas no se
inventa la tabla entera: lo que no está medido cae en el listón por tipo.

También se confirmó que **una habilidad sola afloja desde 17, no desde 16**:
barrido de 13 a 18 en Anotación, Defensa y Portería, los tres saltan en 17. El
16 nunca se había probado y era la sospecha evidente; era falsa.

## Cuánto se le cree, medido en perfiles plausibles

El 2026-10-12 se generaron **60 perfiles realistas** con semilla fija --una
dominante de 8 a 18, una a tres compañeras del puesto, el resto bajo, edad 17
a 33-- y se comparó contra Hattrick dos cosas distintas: la cadena entera de
criterios, y los **tres filtros de habilidad** que es lo único que se le manda
a `transfersearch`.

| | cadena entera | tres filtros |
|---|---|---|
| antes de los arreglos del 12 | 49/60 (82 %) | 57/60 (95 %) |
| con los tres primeros arreglos | 53/60 (88 %) | 59/60 (98 %) |
| con la tapadera de la Anotación | **54/60 (90 %)** | **60/60 (100 %)** |

**Los tres filtros que se le mandan a `transfersearch` salen bien en los
sesenta.** De los seis que quedan en la cadena entera, **tres son orden de la
cola** --habilidades con techo, que nunca se mandan a buscar--, **dos son la
entrada y el techo de la banda del cuarto**, y **uno es el orden de la tercera
y la cuarta**. Ninguno cambia con qué se busca.

Eso responde a la pregunta que importaba: el agujero de FASE Q, el del
mecanismo del orden, **no se está pagando en la búsqueda**.
- **Por qué el empate arriba baja el umbral a 25**, y por qué la cuarta lo baja
  exactamente un punto. Los números están medidos; el motivo es conjetura.
- **Qué pasa por encima de 20** en el balón parado del portero. Ebbesen tiene
  22 anotado y la escala con nombre acaba en divino; el suelo fijo de 14 lo
  tapa, pero no se pudo variar desde el panel.

Nada de esto está extrapolado en el código: va marcado donde toca.

## Un dato que contradice lo que HT Lens hace hoy

El 2026-10-09 HT Lens empezó a **borrar las ventas comparables a las doce
semanas**, sobre la base de que Hattrick hace lo mismo. Su pantalla dice lo
contrario. Los diez comparables de Moisès Llaugé, leídos el 2026-10-10, van del
23 de septiembre al **15 de abril**: el más viejo tiene **unas 25 semanas**, y
Hattrick lo sigue usando para calcular su promedio.

Cuando no tiene nada más fresco, el juego prefiere una venta de hace seis meses
a dejar al jugador sin cifra. Nuestra regla es más estricta que la suya.

Dos detalles más de esa misma lectura: la lista cuenta **ventas, no jugadores**
--el mismo jugador aparece dos veces si se vendió dos veces-- y los diez
comparables tienen especialidades y formas distintas entre sí, lo que confirma
una vez más que ninguna de las dos se filtra.

## La hipótesis que explicaría todo lo que queda abierto

Los agujeros que quedan --el mecanismo del orden, la entrada del tercero, el
listón del dial por pareja, la tapadera de la Anotación-- parecen cuatro cosas
distintas, y puede que sean una sola. El contraejemplo más limpio del sondeo:

| perfil | Lateral 5 |
|---|---|
| Jugadas 16, **Defensa** 10, Lateral 5 | `Lateral <= bueno` (tope) |
| Jugadas 16, **Anotación** 10, Lateral 5 | `Lateral entre débil y bueno` (criterio) |

Misma dominante, una segunda de nivel 10 con el **mismo peso medido** --Defensa
y Anotación comparten peso en el mediocentro--, mismo tercero de nivel 5, y los
dos perfiles holgados. Ninguna función de nivel y peso puede dar dos respuestas
distintas a dos entradas que para ella son idénticas.

**Lo que sí las distingue es el puesto.** Jugadas 16 con Defensa 10 es un
mediocentro *defensivo*; con Anotación 10 es un mediocentro *ofensivo*. Si
Hattrick saca los criterios del **puesto** --de su quincena de puestos, no de
cinco tipos-- se explican de golpe las cuatro cosas:

- el contraejemplo de arriba: son dos puestos, dos plantillas;
- el listón del dial «por pareja» sería un listón **por puesto**, que es mucho
  más natural que una tabla de parejas;
- la intransitividad del orden: añadir una habilidad cambia el puesto, y con
  él la plantilla --un `sorted` no puede permutar a otros dos, un cambio de
  plantilla sí--;
- la tapadera de la Anotación sobre la Defensa sería la frontera entre dos
  puestos de banda.

**Primera prueba, y salió a favor en forma.** La hipótesis predice que el
trato al Lateral cambia al cruzar la frontera entre mediocentro defensivo y
ofensivo. Se barrió una rejilla de Defensa × Anotación con Jugadas 16 y Lateral
5 fijos, y el Lateral entra **sólo con Defensa ≤ 4 y Anotación ≥ 5** --que son
justo las fronteras de *ser criterio*--. La predicción concreta que yo había
hecho, «Anotación > Defensa», era falsa: con Defensa 8 y Anotación 12 no entra.
Pero la forma de la hipótesis aguanta: el Lateral cuenta cuando el perfil es de
mediocentro **ofensivo**. De ahí salió una regla implementable, 93 celdas
medidas y 93 acertadas, que sube el primer tercio de la tanda dura a 20/20.

**Cómo se comprobaría del todo:** sondear por puesto y no por habilidad. Generar
perfiles que caigan claramente en cada puesto conocido y ver si cada grupo da
la misma plantilla --mismo conjunto y mismo orden-- con niveles distintos. Si
es así, lo que hay que medir es una tabla de quince plantillas, no un sistema
de pesos.

**Por qué no está implementado:** sería cambiar el cimiento del módulo con una
hipótesis de dos casos, y lo que hay clava 191 pruebas contra el juego y
acierta los tres filtros en los sesenta perfiles plausibles. El cimiento se
cambia con la tabla medida en la mano, no antes.

## Si Hattrick lo cambia

Ya pasó una vez sin avisar. El sondeo es repetible: el guion está descrito
arriba, los datos crudos se conservan, y las 55 pruebas fijan los criterios
observados contra una fuente ajena a nosotros. Si el juego cambia, las pruebas
caen y se vuelve a sondear.

## Fuentes

- [HTs on Global/Transfer compare](https://wiki.hattrick.org/wiki/HTs_on_Global/Transfer_compare) — flameron (HT), 29-01-2009. La única explicación oficial del mecanismo.
- [Hattrick History](https://www.hattrick.org/en/Help/History.aspx) — sitúa la actualización no documentada en la temporada 69.
- [Transfer compare](https://wiki.hattrick.org/wiki/Transfer_compare) — la página general del wiki; no describe criterios.
- El propio Comparador de Transferencias, sondeado el 2026-10-10.

## Cuánto se separa nuestra escalera de la suya

Medido sobre 33 793 pares sintéticos que **nuestra** escalera acepta, mirando
cuántos llevaría el sello de Hattrick:

| nuestro peso | pares | los enseñaría Hattrick |
|---:|---:|---:|
| 100 % | 10 579 | **84,5 %** |
| 90 % | 3 885 | 61,7 % |
| 85 % | 5 801 | **0,0 %** |
| 80 % | 6 840 | 24,4 % |
| 75 % | 6 688 | 25,1 % |

**El escalón del 85 % no acierta ni uno**, y tiene explicación: es el escalón
que abre la PRIMERA habilidad a ±1 manteniendo la edad clavada. Hattrick nunca
mueve la primera. Así que todo lo que entra por ahí —y sólo por ahí— es gente
que el juego no consideraría comparable en ningún caso.

Los del 80 % y 75 % aciertan uno de cada cuatro porque son escalones de EDAD:
abren el año pero muchos conservan la primaria clavada, y ésos sí pasan.

Y del 100 % nuestro, uno de cada seis no pasaría: son los que tienen una cuarta
habilidad alta, que nosotros ni miramos y a Hattrick le basta para descartarlos.


## Qué se cambió con esto (2026-10-10, decisiones del usuario)

**El 100 % es de Hattrick.** Un comparable vale 100 cuando el propio juego lo
enseñaría, comprobado contra la regla de arriba. Nuestra escalera empieza en
95: «clavado según nosotros, pero el juego no lo enseñaría», que es casi
siempre por una cuarta habilidad alta.

**Se cayó el escalón del 85 %** —edad clavada, primaria a ±1—. De 5 801 pares
que entraban sólo por ahí, Hattrick no habría enseñado ninguno, porque él nunca
mueve la primera habilidad. No era un escalón ancho: era ruido que además
gastaba una petición de cuota cada vez.

**La búsqueda empieza por su ventana.** `plan_de_busqueda` le pide al mercado lo
mismo que pediría el juego, y sólo después recorre nuestra escalera.

**Hacen falta ocho comparables**, no seis. Hattrick usa diez; ocho es el punto
elegido entre parecerse a él y no disparar la cuota.

**Y se levantó el borrado a las doce semanas.** Lo había desde el 2026-10-09,
sobre la base de que el juego hace lo mismo. Su pantalla dice lo contrario, así
que vuelve a mandar `VIDA` sola: cumplirla no borra, deja paso.


## Las ventas guardadas antes del sondeo

Las que ya estaban en el fondo el 2026-10-10 no llevan las siete habilidades,
así que **no pueden llevar el sello de Hattrick** y se miden sólo con nuestra
escalera. Se renuevan solas según entran ventas nuevas.

No se pueden rellenar. Haría falta saber qué habilidades tenía cada vendido **el
día que se vendió**, y CHPP no lo publica: `transfersplayer` devuelve el
identificador del traspaso, el plazo, comprador, vendedor, precio y TSI, y
ninguna habilidad. Pedir `playerdetails` hoy daría las de hoy, que no son las de
entonces. Rellenar con eso sería meter un dato falso justo donde más duele.


## Hasta dónde llega esto, y por qué para ahí

Conviene separar tres cosas que se confunden con facilidad.

**Lo que está derivado y comprobado.** El *qué*: dado un jugador, qué criterios
pone Hattrick. Eso está completo y fijado en 84 casos contra sus propias
respuestas, 33 de ellos predichos a ciegas. Si el juego cambia, las pruebas
caen y se vuelve a sondear.

**Lo que no se puede derivar, ni ahora ni nunca, desde fuera.** El *por qué*
de los números. Por qué el umbral del defensa es 25 y el del extremo 27; por
qué un empate arriba lo baja a 25; por qué una cuarta habilidad lo baja un
punto. Todo eso está **medido y fijado**, y la aplicación lo reproduce. Pero el
motivo vive en el código de Hattrick, y sondear la pantalla no lo revela: sólo
revela el resultado.

Se podría conjeturar --que los puestos raros necesitan aflojar antes, que un
jugador con cuatro habilidades encaja en menos moldes-- y suena razonable. No
está escrito como hecho porque no lo es. **Un número medido vale; una
explicación inventada para ese número no sólo no aporta, estorba**, porque la
próxima persona que lea esto se la creerá.

**Lo que depende de datos que no existen.** Las ventas guardadas antes del
sondeo no pueden llevar el sello, y no es un pendiente: haría falta saber las
habilidades del vendido el día de la venta, y CHPP no las publica. La respuesta
correcta es que se renueven solas, y así está.
