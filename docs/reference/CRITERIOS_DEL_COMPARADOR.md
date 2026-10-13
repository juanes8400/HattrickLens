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

**La Anotación necesita 5 para ser criterio; a las demás les basta 3.** Con
Lateral 16 y sólo una compañera, la Defensa, las Jugadas y los Pases salen como
criterio con un 3, y la Anotación recibe tope con 3 y con 4. Es de la habilidad
y no del tipo: pasa igual en el mediocentro.

**Y hay dos exclusiones más que dependen del nivel.**

**Al extremo, la Defensa no le es criterio si no llega al nivel de la
Anotación** --y sólo cuando esa Anotación es criterio: con Lateral 16, Defensa 3
y Anotación 4, la Defensa 3 sí sale, porque una Anotación de 4 no compite.

**Al mediocentro, el Lateral le pide 7, o 5 si la Anotación llega a 5 y la
Defensa no pasa de 4** --es decir, si la Anotación es criterio y la Defensa no--.
Es la lectura de mediocentro ofensivo, y está medida en unas noventa celdas.

**Y ahí acaba la lista: el defensa y el delantero no tienen nada propio.** Se
les barrió igual --el Lateral del defensa y las Jugadas del delantero, con la
dominante sola y con cada posible segunda al lado-- y entran con 3 de segunda y
5 de tercera, que es la regla general. El inventario de entradas queda cerrado
para los cuatro tipos de campo.

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

**Y es el mecanismo, no un ajuste.** Lo dice la fuente de 2009, literal:

> *«The main logic of the system is to check which player type is compared.
> Then a set of secondary tertiary and quartile skills are chosen. (…) In short
> the list of skills is sorted by the initial order having importance unless the
> skills are higher then the skill before them in the initial list by more then
> the difference in the initial skills.»*

Desmontado: `B` adelanta a `A` ⟺ `nivel(B) − nivel(A) > importancia(B) −
importancia(A)`, que es ordenar por `nivel − importancia`. Lo que el texto **no**
dice es cuántas listas iniciales hay, y ahí estaba el error: yo tenía cinco
tipos y asumí cinco listas.

#### El extremo tiene dos listas

| cuándo | lista |
|---|---|
| Pases, Defensa y Anotación **las tres** en el conjunto | `Lat 0, Jug 1, Ano 2, Pas 3, Def 4` |
| cualquier otro caso | `Lat 0, Jug 1, Pas 2, Def 3, Ano 3` |

Con eso salen **los quince subconjuntos** del extremo de FASE Q, incluidos los
dos que durante dos días parecieron demostrar que ningún orden por clave podía
funcionar:

| perfil | orden | por qué |
|---|---|---|
| Pases 9, Anotación 9 | Lateral, **Pases, Anotación** | la Defensa está fuera → lista normal |
| Pases 9, Anotación 9, Defensa 9 | Lateral, **Anotación, Pases**, Defensa | las tres dentro → la otra lista |

No era una lista que se contradice: eran dos. Añadir un elemento sí puede
permutar a otros dos **si añadirlo cambia de lista**.

**Y hay una predicción cumplida**, que es lo que separa esto de un ajuste. Si lo
que cambia la lista es que la Defensa *entre en el conjunto* --y no que llegue a
un nivel-- entonces con la Anotación en 7 el giro debe caer en Defensa 7 y no en
9. Cae en 7:

| perfil | Def 4-6 | Def 7 | Def 8 | Def 9 |
|---|---|---|---|---|
| Lat 16, Pas 7, Ano 7 | Lat Pas Ano | **Lat Ano Pas Def** | Lat Ano Def Pas | Lat Def Ano Pas |
| Lat 16, Pas 9, Ano 9 | Lat Pas Ano (hasta 8) | — | — | **Lat Ano Pas Def** (en 9) |

**La condición no es «entra la Defensa» a secas.** Con esa condición se rompen
siete casos ya medidos, y los siete tienen en común que la Anotación no está en
el conjunto. Se puede comprobar antes de ordenar porque el corte usa la
plantilla y no los pesos, así que no hay círculo.

#### Y el mediocentro también, en el sentido contrario

| cuándo | lista |
|---|---|
| la Defensa **está en el conjunto** y `Defensa ≥ max(5, Anotación − 3)` | `Jug 0, Pas 1, Def 2, Ano 3, Lat 3` |
| cualquier otro caso | `Jug 0, Pas 1, Def 2, Ano 2, Lat 3` |

#### Y sólo esos dos tipos tienen dos listas

| tipo | la Defensa es | listas |
|---|---|---|
| extremo | ajena, y puede entrar | **dos** |
| mediocentro | ajena, y puede entrar | **dos** |
| defensa | **la suya** | una |
| portero | su segunda fija | una |
| delantero | **no le entra nunca** (exclusión por tipo) | una |

Medido el 2026-10-12 con dos barridos diseñados para que las dos listas
hipotéticas discrepasen. En el **defensa** --`Def16 Jug10 Pas9` con el Lateral de
0 a 12-- el orden `Jug, Pas` **no gira en ningún punto**, y el Lateral adelanta
en 11, que es justo donde lo predicen los pesos normales. En el **delantero**
--`Ano16 Pas9 Lat10` con la Defensa de 0 a 11-- la Defensa se queda **siempre**
en el montón.

Eso cierra la pregunta de por qué las dos exclusiones en espejo no se unifican:
**no son dos casos de una regla general que se me escapa, son los dos únicos
tipos donde la conmutación puede ocurrir.** Y que haya una regla por tipo encaja
con el texto de 2009, que habla de elegir un conjunto *según el tipo*.

Al extremo la Defensa le **sube** la Anotación; al mediocentro se la **baja**, que
es lo que cabe esperar de un mediocentro defensivo. Medido en cuatro barridos
con la frontera a los dos lados:

| perfil | gira en Defensa |
|---|---|
| Jug 16, Pas 7, Ano 8 | 5 |
| Jug 16, Pas 9, Ano 10 | 7 |
| Jug 16, Pas 12, Ano 13 | 10 |
| Jug 16, Lat 8, Ano 8 | 5 |

Los tres primeros **no bastan** para sacar el umbral: en los tres la Anotación
era `Pases + 1`, así que `Def ≥ Pases − 2` encajaba igual de bien. El cuarto los
separa, y se hizo por eso: sin Pases, `Pases − 2` daría umbral −2 y giraría
siempre, y Hattrick gira en 5. Predicción hecha antes de medir, y cumplida.

Esto arregla la otra contradicción de FASE Q --`Jug16 Pas7 Def9 Ano8` sale
`Jug Def Pas Ano`-- que era la que exigía «Anotación con peso 3» rompiendo
«Anotación con peso 2»: son dos listas, y cada una tiene su peso.

**La habilidad que da el tipo va siempre la primera**, aunque otra tenga más
nivel. Por eso un Pases 16 con todo lo demás a cero empieza por
`Lateral = nulo`: clavar el Lateral es lo que separa a un pasador de un extremo.

### 4. Qué operador le toca a cada puesto

| puesto | regla |
|---|---|
| **1º** | siempre **exacto** |
| **2º** | **techo** por debajo de 3 (2 en el portero) · **exacto** hasta 9 (6 en el portero) · **banda `[v−1, v+1]`** desde 10 (7 en el portero) |
| **3º** | cae a techo por debajo de 5 · **banda** de 5 a 10 · **suelo `≥ v`** desde 11. Y **una 1ª débil le quita sitio**: ver abajo |
| **4º** | existe de 6 en adelante, y en 5 sólo si la **2ª habilidad de la plantilla** no pasa de 7 (ver «Lo que queda desconocido»). Banda estrecha como el 3º por debajo de 8, y ancha `[v−2, v+3]` de 8 en adelante, **cortada arriba por el nivel de la 1ª**: con Defensa 9 y las otras tres a 8 sale `Lat 6-9`, y subiendo sólo la Defensa a 10 sale `Lat 6-10`. Un cuarto puesto no puede pedir más de lo mejor que tiene el jugador |
| **resto** | **techo** |

La banda del 3º mide `[v−1, v+1]` con la búsqueda ajustada y `[v−1, v+2]` con la
búsqueda holgada.

**Una primera débil le quita sitio al tercero, en dos escalones.** Sólo pasa
cuando la 2ª habilidad SUPERA a la 1ª, que es el único caso en que se ha visto:

| nivel de la 1ª | qué le pasa al 3º que la alcanza |
|---|---|
| ≤ 5 | **no llega a ser criterio**: recibe techo (`Lat5 Pas13 Def5` → `Def <= 5`) |
| 6 | es criterio, pero su banda **se corta en la 1ª** (`Lat6 Pas13 Def6` → `Def 5-6`) |
| ≥ 7 | **no se corta nada**, ni cuando la banda se sale por encima de la 1ª (`Lat7 Pas13 Def7` → `Def 6-8`) |

Barrido el 2026-10-12 con la 1ª y la 3ª igualadas en 6, 7, 8, 9 y 10. Y la
compresión **no depende del hueco**: con Lateral 6 y Defensa 6, la Defensa sale
`5-6` tanto con los Pases en 8 como en 13 como en 20.

El escalón de ≤ 5 tiene un dominio de **una sola casilla** (1ª en 5 y 3ª en 5),
y no por falta de medidas: con la 3ª por encima de la 1ª se reordenan los
puestos y la 3ª pasa a ser 1ª, y con la 3ª por debajo no llega al umbral de
entrada. No hay más casillas que medir.

**Asimetría medida, y sin explicar:** el **4º** puesto sí se corta en la 1ª
siempre (medido con la 1ª en 9 y en 10), mientras que el 3º sólo se corta con
la 1ª en 6. Son dos reglas distintas para dos puestos, y no se ha encontrado la
forma de unificarlas: la banda holgada del 3º con la 1ª en 10 sale `9-12`, que
se pasa de la 1ª sin que nadie la corte.

**La segunda se abre a banda antes de tiempo** si la tercera llega a 7, si
**la cuarta llega a 5 y la segunda a 8**, o si **empata con la primera y las dos
llegan a 8**.

Lo de la cuarta lo decía la misma fuente de 2009 --*«or if the third and fourth
skills are quite high and secondary is high»*-- y estuvo dos días dado por
refutado: los dos barridos que lo buscaban tenían la segunda en **7**, justo por
debajo de la frontera, así que salían clavados los dos. Medido ahora con la
segunda en 6, 7, 8 y 9 contra la cuarta en 0, 4, 5 y 6, y no depende de la
primera (abre igual con la primera en 12, 16 y 20).
Lo decía 2009: *«lo mismo ocurre si la tercera es alta»*; el umbral son siete, y
eso no lo decía.

El del empate sí tiene frontera medida (2026-10-12, con la 1ª y la 2ª igualadas
y sin tercera que estorbe): **clavada** en 6 y en 7, **banda** en 8 y en 9. El
único caso que sostenía esta regla antes era el (8,8,6), que cae justo encima de
la frontera, y por eso parecía que el empate abría siempre.

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

holgado  ⟺  rareza ≥ umbral   o   nivel de la 1ª ≥ 17
```

El `≥ 17` es **de la primera, no del nivel más alto que tenga el jugador**. Se
midió con (17,5) y (18,0), y en los dos el 17 era la primera; generalizarlo a
cualquier habilidad fallaba en tres medidas del 2026-10-12 --`Lat6 Def6 Pas20`,
`Lat5 Def5 Pas18` y `Lat6 Pas17`, los tres **ajustados** pese a llevar un 17 o
más--. La rareza ya los separa sola: dan 26, 23 y 23, por debajo del 27 de su
pareja, mientras que `Lat7 Def7 Pas20` llega a 28 y sí afloja.

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

**La asimetría de los 35 está barrida**, no es un punto suelto: el 2026-10-13 se
midieron los dos perfiles de siempre a los 33, 34, 35, 36 y 40, y en **holgado**
la edad sigue siendo ±1 a los 35 (`34-36`) y a los 36 (`35-37`). El suelo abierto
es sólo del modo ajustado.

**Al PASADOR no se le abre a los 32**: a quien lo más alto que tiene son Pases
la edad le aguanta clavada hasta los 34. Dándole la vuelta al mismo par de
habilidades cambia el resultado --Pases 13 y Jugadas 7 da `= 33`, y Jugadas 13
con Pases 7 da `32-34`--. Es la misma excepción que le fuerza el primer
criterio, asomando por otro sitio.

**A los 17, y sólo a los 17**, aparece además un tope de días (`Días <= 24`).
El número es **fijo**: se pidió el mismo perfil de 17 años desde la ficha de un
jugador de 2 días y desde la de uno de 20, y las dos veces salió 24.

## La única parte de la regla que no se aplica

A los 17 años Hattrick añade un **tope de días**: `Días <= 24`. Está en
`Criterios.tope_de_dias`, pero **nadie lo consume**.

**Y es una constante**, barrido el 2026-10-13: sale `Días <= 24` en tres perfiles
distintos y en los **dos modos del dial** --la holgura no lo ensancha-- y a los
18 años no hay tope ninguno. Eso simplifica la decisión: no hay fórmula que
derivar, sólo un número que aplicar cuando se tenga el dato.

- La **búsqueda** no lo manda, y eso está bien: `transfersearch` acepta años y
  no días, y pedir un superconjunto no hace daño.
- El **sello del 100 %** tampoco lo comprueba, y ahí sí importa: a un jugador
  de 17 años y 80 días Hattrick no lo enseñaría y nosotros le damos el sello.

**Por qué no está arreglado:** hace falta el dato. Ni `Candidato` ni
`market_sales` guardan los días, aunque el parser de CHPP ya los lee
(`age_days`). Arreglarlo es una columna nueva y una migración --igual que se
hizo con `skills_json`--, y aplicarlo sólo a los candidatos vivos dejaría a la
misma venta con sello antes de guardarse y sin sello después, que es peor que la
inexactitud. **Afecta sólo a comparables de 17 años**, y queda a decisión de
quien lleve el producto.

## Lo que NO se compara

Forma, resistencia, especialidad, experiencia, liderazgo, carácter,
nacionalidad, TSI, y el balón parado de los jugadores de campo. Coincide con lo
que declararon en 2009, y con lo que HT Lens ya excluía.

## Validado contra las 25 fichas reales, por la vía normal

El 2026-10-12, después de los cuatro cambios de regla de ese día, se pidieron
las 25 fichas de la plantilla **sin tocar el panel «Editar búsqueda»** y se
comparó la cadena entera:

**25 de 25, enteras, incluido el montón.** Cubren de la edad 20 a la 45, los
cinco tipos, un portero con balón parado 20 y tres jugadores por encima de los
35. Son perfiles que nadie diseñó para probar nada, que es lo que las hace
valer, y quedan fijadas como `LAS_FICHAS_REALES`.

Esto es **comprobar, no ajustar**: ninguna constante del motor sale de ahí.

## Cuántos de sus números están de verdad medidos

Que el banco esté verde tienta a creer que los números del motor están medidos.
No lo están todos: un número puede caer **dentro de un intervalo** que el banco
no distingue.
[`cuanto_esta_fijado_cada_numero.py`](sondeo-comparador/cuanto_esta_fijado_cada_numero.py)
barre cada constante y da el tramo que mantiene el banco intacto, y para los
que sólo quedan acotados saca el perfil que los separaría.

**La auditoría del 2026-10-12 encontró cinco acotados, se midieron los cinco, y
tres estaban mal:**

| número | antes | medido |
|---|---|---|
| `HABILIDADES_QUE_CUENTAN` | 4 | **4** ✓ |
| `BP_BANDA_MAXIMA` | 15 | **15** ✓ |
| `LATERAL_DEL_MEDIO_SIN_AYUDA` | 7 | sigue 7, pero lo que estaba mal era **el hueco a la dominante**: ver abajo |
| `UMBRAL_CON_EMPATE_ARRIBA` | 25 | **26** |
| `DESCUENTO_DEL_BALON_PARADO` | 10 | **9** |

Y de paso apareció una cuarta corrección que no se buscaba: con una cuarta de 8
salió `[6,10]` y no `[6,11]`, así que **la banda ancha del cuarto también sigue
al dial** (`v+3` holgado, `v+2` ajustado). Eso explica además las cuatro medidas
viejas del cuarto puesto sin tocarlas: las cuatro eran holgadas.

**El caso del Lateral merece contarse, porque es el error más instructivo del
día.** La consulta decía «el umbral es 6, no 7», y era verdad en lo medido y
falsa como regla:

| perfil | Hattrick |
|---|---|
| `Jug16 Pas9 Lat6` (rejilla de 90 celdas, 2026-10-11) | el Lateral **no** entra |
| `Jug8 Lat6`, nada más (2026-10-12) | el Lateral **sí** entra |

No se contradicen: la rejilla llevaba **siempre** una compañera y la dominante
entre 12 y 20; la consulta nueva no llevaba ninguna. Lo que decide es el **hueco
a la dominante**, y son **cinco niveles**: con el Lateral en 6 y nada más, entra
hasta Jugadas 11 y se cae desde Jugadas 12. Los dos conjuntos de medidas **no se
solapaban en la dominante**, y la frontera caía justo en el hueco entre ellos.

**Pasadas siguientes de la auditoría.** La segunda dejó un solo número de regla
acotado, `DESCUENTO_DEL_BALON_PARADO` (5-9), y la consulta que lo separaba
--`Por8 BP12`-- dio la predicción de **9** exacta. La tercera destapó el **quinto
punto ciego del banco**: daba las dos constantes del tope de días como «sin
fijar» cuando estaban medidas en cuatro perfiles esa misma mañana, porque el tope
de días **no sale en la cadena de criterios** y el banco puntúa cadenas.

Con eso dentro, **39 de los 40 números del motor están clavados**. El único que
queda, `MAXIMO_DE_LA_ESCALA`, no es una regla: es el tope con el que se rellena
el campo `maximo` de un criterio `>=`, y la cadena no lo enseña. Que no se pueda
fijar midiendo es lo correcto.

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

**No queda ninguna observación sin reproducir**: el banco está en 476/476 con la
lista de pendientes vacía. Eso no quiere decir que el motor sea el mecanismo de
Hattrick; quiere decir que no hay contraejemplo conocido. Lo que sigue abierto
es concreto y corto:

- **Si hay UNA regla detrás de las dos exclusiones en espejo, o una por tipo.**
  Siete candidatas a unificarlas fallaron
  ([`unificar_las_dos_exclusiones.py`](sondeo-comparador/unificar_las_dos_exclusiones.py)),
  y todas se atascan en que la fuerza del empate difiere por tipo. Pero los dos
  barridos del defensa y del delantero explican **por qué no hay más que dos**:
  son los dos únicos tipos donde la Defensa puede ser criterio sin ser la
  habilidad propia. Así que puede que no exista una regla general, y que sea una
  por tipo, que es lo que dice el texto de 2009.
- **La Defensa del portero por encima de 9.** Está barrida del 1 al 9 --clavada
  hasta 6, banda desde 7-- y de 10 arriba el motor le aplica la regla general
  del segundo puesto por extensión, no por medida. Lo interesante sería que
  apareciese un **suelo**, como le pasa al tercer puesto desde 11 y al balón
  parado desde 16; si lo hay, el motor falla ahí y no se notaría, porque un
  portero con Defensa 12 o más es raro y no hay ninguno en las 25 fichas reales.
  El sondeo está escrito con su predicción en FASE AO: cinco consultas.
- **Por qué el escalón del sesgo del portero está en Defensa 12.** La tabla
  entera está medida de 1 a 20; el motivo, no. Por encima de 20 no se sondeó.
- **El tope de días de los 17 está medido y no se consume.** Hace falta una
  columna y una migración, y es decisión del producto. Está contado abajo, en «La
  única parte de la regla que no se aplica».

**Y de los 40 números del motor, 36 están clavados por las medidas.** Los otros
cuatro no son reglas: uno es de representación y tres son del tope de días, que
no se consume.
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

**Perfiles plausibles** --una dominante, una a tres compañeras del puesto, el
resto bajo--:

| | cadena entera | tres filtros |
|---|---|---|
| antes de los arreglos del 12 | 49/60 (82 %) | 57/60 (95 %) |
| con los tres primeros arreglos | 53/60 (88 %) | 59/60 (98 %) |
| con la tapadera de la Anotación | **54/60 (90 %)** | **60/60 (100 %)** |

**Perfiles duros** --los que buscan puntos ciegos: Portería alta en jugadores de
campo, empates exactos, perfiles planos y de una sola habilidad, edades de
borde--:

| | cadena entera | tres filtros |
|---|---|---|
| al abrir la tanda | 49/60 (82 %) | 56/60 (93 %) |
| ahora | **55/60 (92 %)** | **59/60 (98 %)** |

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

> **2026-10-12: esta hipótesis ya no es una hipótesis, es el mecanismo, y la
> fuente de 2009 lo dice.** Hattrick ordena por `nivel − importancia` sobre una
> **lista inicial por tipo**, y lo que faltaba era que hay **más listas que
> tipos**: el extremo tiene dos, y con la segunda salen los quince subconjuntos
> de FASE Q que esta sección presentaba como imposibles. Está contado arriba, en
> «El orden de los criterios», con la predicción que se cumplió. Lo que sigue se
> conserva porque el razonamiento es el que llevó allí, y porque la parte del
> mediocentro **sigue abierta**: le faltaría su segunda lista.

Los agujeros que quedan --la entrada del tercero y del cuarto, el listón del
dial por pareja, la tapadera de la Anotación-- parecen cosas distintas, y puede
que sean una sola. El contraejemplo más limpio del sondeo:

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

**Hubo una segunda prueba y la retiré.** Conté cuántos órdenes de prioridad
distintos hacen falta por tipo y me salió que cada uno necesita menos que los
puestos que Hattrick tiene en su zona. Lo presenté como apoyo y **no lo es**:
dos listas que ordenan distinto un par compartido no exigen dos puestos si los
niveles ya explican la diferencia --Jugadas 10 con Lateral 7 da un orden y
Jugadas 7 con Lateral 10 el contrario, sin que haya dos puestos--. Lo que esa
cuenta medía era cuántos patrones de nivel aparecen en los datos. Los cinco
órdenes del defensa, que parecían cinco puestos, son cinco patrones de nivel y
el motor actual los reproduce los cinco.

**Lo que sí salió de ahí, y va contra los atajos:** el orden **no** es función
del conjunto de criterios. De 17 grupos (tipo, conjunto) con tres o más
criterios, siete salen en más de un orden. Si los criterios salieran de un
puesto y el puesto del conjunto, lo sería; luego el puesto, si existe, depende
también de los niveles.

Lo que sostiene la hipótesis sigue siendo el contraejemplo de arriba, que
descarta el modelo de pesos como mecanismo, y la frontera del Lateral del
mediocentro, que cae justo donde la Anotación es criterio y la Defensa no.

**Cómo se comprobaría del todo:** sondear por puesto y no por habilidad. Generar
perfiles que caigan claramente en cada puesto conocido y ver si cada grupo da
la misma plantilla --mismo conjunto y mismo orden-- con niveles distintos. Si
es así, lo que hay que medir es una tabla de quince plantillas, no un sistema
de pesos.

**Por qué no está implementado:** sería cambiar el cimiento del módulo con una
hipótesis de dos casos, y lo que hay clava 191 pruebas contra el juego y
acierta los tres filtros en los sesenta perfiles plausibles. El cimiento se
cambia con la tabla medida en la mano, no antes.

## El banco: avanzar sin gastar consultas

Hattrick estrangula a las ~300 consultas y a partir de ahí devuelve 200 con una
página sin criterios. Con la cuota agotada, medir produce datos falsos, que es
peor que no tener datos.

Para eso está [`sondeo-comparador/banco.py`](sondeo-comparador/banco.py): junta
las ~180 observaciones que las pruebas ya guardan y puntua el motor contra
todas. Un candidato sólo vale si **mantiene el total medido y sube los
pendientes**; si baja aunque sea uno, se descarta.

El 2026-10-12 el banco encontró **dos arreglos reales con la cuota ya agotada**:
el corte del orden por plantilla y el corte condicional de la banda de la
tercera. En los dos casos mi análisis a mano decía lo contrario de lo que dijo
el banco, y tenía razón el banco.

**Y el mismo día, con sesión nueva, el banco atrapó el límite de lo que puede
hacer:** de los dos arreglos que encontró a ciegas, uno --el corte de la banda--
estaba *mal generalizado*, y el banco lo dio por bueno porque las 236
observaciones que tenía no contenían ninguna con la primera en 7 o más. Un banco
sólo defiende lo que ya se midió; no sabe lo que falta. Las 23 consultas de FASE
AD lo subieron a 259 y el corte pasó a tener frontera.

## Cuánto sostiene cada regla

El motor es un montón de reglas sacadas de mediciones distintas, y no todas
pesan lo mismo.
[`cuanto_sostiene_cada_regla.py`](sondeo-comparador/cuanto_sostiene_cada_regla.py)
las quita de una en una y cuenta cuántos de los **476** casos medidos dejan de
salir:

| al quitar | se rompen |
|---|---|
| las exclusiones por tipo | 221 |
| la regla del Lateral del mediocentro | 31 |
| el sesgo del portero sobre la defensa | 20 |
| que el cuarto entre solo desde 6 | 19 |
| los pesos del mediocentro | 19 |
| que la tercera en 7 abra la segunda | 16 |
| la tapadera de la Anotación al extremo | 14 |
| que la Anotación pida cinco | 11 |
| los pesos del extremo | 11 |
| la segunda lista del extremo | 9 |
| la tabla del dial por pareja | 9 |
| la cola propia del mediocentro | 9 |
| el descuento del balón parado | 8 |
| las dos exclusiones en espejo | 8 |
| el desempate propio del extremo | 6 |
| el umbral de la segunda lista del mediocentro | 6 |
| que una habilidad de 17 afloje sola | 5 |
| que la primera en 6 corte la banda del tercero | 5 |
| la segunda lista del mediocentro | 5 |
| el hueco de cinco que hace periférico al Lateral | 5 |
| que el mediocentro pierda la Anotación bajo el Lateral | 5 |
| que la primera en 5 no sostenga tercero | 3 |
| que el extremo pierda los Pases bajo la Anotación | 3 |
| que el empate abra la segunda | 2 |
| el listón de 26 con las dos primeras empatadas | 1 |
| **la posición de la Portería en el desempate** | **0** |

**Y las reglas con umbral se prueban también por el otro lado**, que es lo que
separa un umbral medido de uno inventado:

| al generalizar | se rompen |
|---|---|
| cortar la banda del tercero **siempre**, no sólo con la 1ª en 6 | 5 |
| que el cuarto entre **siempre desde 5**, sin mirar a la compañera | 4 |
| abrir la segunda **con cualquier empate**, no sólo desde 8 | 3 |

**La tabla se ha arreglado dos veces, las dos por lo mismo:** le faltaban las
29 filas de órdenes del extremo, y luego las 70 del Lateral del mediocentro.
Un banco incompleto miente con más aplomo que no tenerlo.
**Para qué sirve:** dice en qué apoyarse y en qué no. Las exclusiones por tipo
sostienen 221 casos --tocarlas es tocar el motor entero--; la tabla del dial
por pareja sostiene dos, así que si una medición la contradice no hay que
defenderla. Y la regla que durante dos días «descansaba en un caso» sostiene
ahora tres, con sus cuatro casillas vecinas medidas.

**El único cero es información muerta, no una regla sin apoyo:** `_tipo` saca la
Portería de la lista y la compara aparte, así que su sitio en la tupla no lo lee
nadie. Lo que la medición sostiene es el `>` estricto --con Jugadas 10 y
Portería 10 sale mediocentro-- y eso queda dicho donde toca.

## Si Hattrick lo cambia

Ya pasó una vez sin avisar. El sondeo es repetible: el guion está descrito
arriba, los datos crudos se conservan, y las 55 pruebas fijan los criterios
observados contra una fuente ajena a nosotros. Si el juego cambia, las pruebas
caen y se vuelve a sondear.

## Qué parte del texto de 2009 sigue viva

Es la única fuente general que existe, y el 2026-10-12 se contrastó entera
(`sondeo-comparador/fase-a.txt`, FASE AK).

**La estructura sobrevivió: catorce cláusulas, catorce vivas.** El tipo de
jugador, el conjunto de habilidades elegido por tipo, la ordenación por
`nivel − importancia`, los rangos de la segunda cuando es muy baja o muy alta,
la tercera alta que la abre, la cuarta que la abre con la segunda alta, lo que
no se compara, el portero con defensa y balón parado, y la edad exacta que
importa en los jóvenes.

**Los números no.** Tres contradicciones firmes, las tres de valor:

| dice 2009 | está medido |
|---|---|
| la 5ª y la 6ª **siempre** por debajo de débil | los techos siguen al nivel desde 5: `v+1` ajustado, `v+2` holgado |
| la 3ª y la 4ª **siempre** por rangos | de 11 en adelante la 3ª es un **suelo**, no un rango |
| el balón parado del portero, rangos **en todos los casos** | de 16 en adelante es un suelo fijo en 14. Y las anchuras cambiaron: en 2009 un balón parado 9 y uno 11 daban los dos «7 a 16»; hoy dan 6-12 y 8-14 |

La actualización no documentada de la temporada 69 **reafinó valores y no tocó
el mecanismo**.

**De ahí la regla de uso del texto**, que funcionó dos veces el mismo día: vale
para **la forma** de una regla, no para su **número**. Cuando dice que algo pasa
«si es alto», hay que creerle que pasa y medir el umbral; cuando da un número o
un ejemplo concreto, hay que desconfiar.

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
