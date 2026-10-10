# Los criterios del Comparador de Transferencias de Hattrick

**Fecha del sondeo:** 2026-10-10
**Estado de la evidencia:** derivado del propio juego, preguntándoselo
**Validación:** 55 casos fijados en `backend/tests/test_criterios_hattrick.py`,
de los cuales 15 se predijeron a ciegas antes de consultarlos y acertaron los 15.

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

Se le hicieron **unas 520 consultas** con perfiles sintéticos, moviendo un eje
cada vez y buscando las fronteras por bisección. Los datos en bruto, consulta a
consulta, están en [`sondeo-comparador/`](sondeo-comparador/).

Dos comprobaciones de control, antes de nada:

- **La ficha desde la que se abre el panel no influye.** El mismo perfil
  inventado, enviado desde la ficha de un portero y desde la de un defensa,
  devuelve criterios idénticos.
- **Hattrick recalcula de verdad.** Cambiar una sola habilidad cambia los
  criterios; el panel no se limita a reenviar lo que le metes.

Esto cumple [`AGENTS.md`](../../AGENTS.md): la regla no se ajustó contra la
plantilla del propietario, se le preguntó al juego, que es la fuente general que
esa norma exige. Los perfiles sondeados son inventados.

## La regla

### 1. El tipo de jugador

Lo decide **la habilidad más alta**, con una excepción: **Hattrick no tiene
puesto de pasador**. Si lo que más tiene es Pases, el tipo lo da la mejor de las
demás. Un Pases 15 con Jugadas 12 se trata como mediocentro.

A igualdad de nivel el orden es
**Lateral › Anotación › Portería › Defensa › Jugadas › Pases**.

### 2. La plantilla de cada tipo

Cada tipo mira seis habilidades, en este orden:

| domina | 1º | 2º | 3º | 4º | 5º | 6º |
|---|---|---|---|---|---|---|
| Portería | Portería | Defensa | **Balón parado** | Lateral | Anotación | Jugadas |
| Defensa | Defensa | Pases | Jugadas | Lateral | Anotación | Portería |
| Jugadas | Jugadas | Pases | Defensa | Lateral | Anotación | Portería |
| Lateral | Lateral | Jugadas | Pases | Defensa | Anotación | Portería |
| Anotación | Anotación | Pases | Lateral | Jugadas | Defensa | Portería |

El portero es el único que mira **balón parado**. En un jugador de campo no
influye en nada: con Defensa 14 y Jugadas 10, un balón parado de 0, de 12 o de
20 da exactamente los mismos criterios.

### 3. El orden de los criterios

Se ordenan por **`nivel − posición en la plantilla`**, de mayor a menor. Eso
significa que **adelantar cuesta tantos niveles como puestos haya que subir**:
con Pases en 7, Jugadas --que va justo detrás-- adelanta con 8, pero Lateral
--dos puestos más atrás-- necesita 9.

Es la regla que flameron describía en 2009 sin dar el número.

**La habilidad que da el tipo va siempre la primera**, aunque otra tenga más
nivel. Por eso un Pases 16 con todo lo demás a cero empieza por
`Lateral = nulo`: clavar el Lateral es lo que separa a un pasador de un extremo.

### 4. Qué operador le toca a cada puesto

| puesto | regla |
|---|---|
| **1º** | siempre **exacto** |
| **2º** | **techo** por debajo de 3 (2 en el portero) · **exacto** hasta 9 (6 en el portero) · **banda `[v−1, v+1]`** desde 10 (7 en el portero) |
| **3º** | cae a techo por debajo de 5 · **banda** de 5 a 10 · **suelo `≥ v`** desde 11 |
| **4º** | sólo existe si llega a 5. Banda estrecha como el 3º por debajo de 8, y ancha `[v−2, v+3]` de 8 en adelante. Si empata con la **primera** --o sea, si las cuatro valen lo mismo-- se queda pegada por debajo: `[v−2, v]` |
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

**Con las dos primeras habilidades empatadas el umbral baja a 25**, sea el tipo
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
32 y más  ->  ±1 SIEMPRE, aunque el resto de la búsqueda siga ajustada
```

**A los 17, y sólo a los 17**, aparece además un tope de días (`Días <= 24`).

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

- **De dónde sale el `Días <= 24`** de los 17 años: el panel no tiene campo de
  días, así que no se pudo mover.
- **Qué hace un cuarto puesto de 8 o más con la búsqueda ajustada**: todos los
  que se midieron ahí arriba cayeron del lado holgado.
- **Por qué el empate arriba baja el umbral a 25 y no a otra cosa.** El número
  está medido; el motivo es conjetura.

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
