# Training Engine

## Alcance

El motor estima el entrenamiento técnico del primer equipo, registra pops
confirmados y proyecta niveles futuros. La estructura de las pantallas puede
inspirarse en Hattrick Control; la matemática procede de la fórmula comunitaria
pública de HT-Tools.

No es código del servidor de Hattrick. Los datos privados del manager se usan
para aplicar y contrastar la fórmula, nunca para ajustar sus coeficientes.

## Entradas

- Tipo de entrenamiento (`TrainingType`, leído de `training.xml`).
- Intensidad y porcentaje dedicado a resistencia (`training.xml`).
- Nivel del entrenador y niveles combinados de hasta dos asistentes
  (`stafflist.xml`).
- Edad, nivel entero de habilidad y minutos/posición del jugador.
- Subnivel decimal opcional. CHPP no lo publica; si no se conoce se usa 0,0.

El liderazgo del entrenador se muestra como información del club, pero no
forma parte de la velocidad de entrenamiento.

## Fórmula 1: HT-Tools

Primero se calcula el coeficiente semanal efectivo:

```text
K = K_entrenamiento × K_entrenador × K_asistentes
    × intensidad/100 × (1 − resistencia/100) × exposición
```

El trabajo acumulado de una habilidad es una función por tramos:

```text
F(s) = (s^1,72 − 1) / (6,0896 × 1,72)                     si s < 9
F(s) = 2,45426 + (s − 5)^1,96 / (4,7371 × 1,96)           si s ≥ 9
```

La fecha del pop se obtiene sobre el reloj de edad público:

```text
reloj_pop = reloj_edad(edad)
           + (F(nivel + 1) − F(nivel + subnivel)) / K

semanas = 16 × (reloj_edad_inverso(reloj_pop) − edad)
```

Consecuencias importantes:

- el nivel sí modifica el costo: 5→6 no tarda lo mismo que 14→15;
- el subnivel solo reduce el trabajo restante del nivel actual;
- la edad no se modela con un `+6%` lineal, sino con su reloj tabulado;
- Pases cortos y Pases largos tienen coeficientes diferentes.

## Coeficientes por tipo

| TrainingType | Modo | K |
|---:|---|---:|
| 2 | Balón parado | 0,941 |
| 3 | Defensa | 0,206 |
| 4 | Anotación | 0,218 |
| 5 | Lateral | 0,315 |
| 6 | Tiros | 0,097 |
| 7 | Pases cortos | 0,237 |
| 8 | Jugadas | 0,220 |
| 9 | Portería | 0,335 |
| 10 | Pases largos | 0,178 |
| 11 | Posiciones defensivas | 0,094 |
| 12 | Ataques laterales | 0,219 |

Resistencia no se calcula con esta fórmula técnica; conserva su motor de
referencia separado.

## Entrenador y asistentes

`StaffLevel` 1–5 se convierte directamente a la escala 4–8 de la fórmula.

| Escala de fórmula | K entrenador |
|---:|---:|
| 4 | 0,774 |
| 5 | 0,867 |
| 6 | 0,943 |
| 7 | 1,000 |
| 8 | 1,045 |

```text
K_asistentes = 0,66 + 0,032 × suma_de_niveles
```

La suma está limitada a 10: dos asistentes de nivel 5. No es el número de
asistentes.

## Edad

El reloj acumulado para edades enteras 17–34 es:

```text
0,000; 16,000; 31,704; 47,117; 62,246; 77,094; 91,668;
105,972; 120,012; 133,791; 147,316; 160,591; 173,620;
186,408; 198,960; 211,279; 223,370; 235,238
```

Lens interpola los días entre cumpleaños. Para mayores de 34 prolonga el
último tramo publicado y muestra esa limitación; no ajusta una curva con datos
privados.

## Minutos y posiciones

```text
exposición = min(minutos / 90, 1) × proporción_de_la_posición
```

- 90 minutos en una posición completa: 100%.
- 45 minutos en una posición completa: 50%.
- 90 minutos en una posición parcial: 50%.
- una posición no entrenable: 0%.

## Habilidad entrenada por jugador vendido

Para cada venta, Lens compara el primer snapshot histórico disponible del
jugador con el último snapshot cuya fecha sea anterior o igual a la venta. El
aumento de cada habilidad es:

```text
aumento = último nivel observado antes de vender − primer nivel observado
```

Las lecturas posteriores a la venta quedan fuera. Se asigna como **habilidad
entrenada** aquella que tenga el mayor aumento positivo único entre:

```text
Portería, Defensa, Jugadas, Lateral, Pases, Anotación y Balón parado
```

Si no aumentó ninguna o el máximo individual empata, se toman todos los
jugadores vendidos en la misma temporada Hattrick. Para cada habilidad se
suman primero los niveles observados de esos jugadores. Si dos o más
habilidades empatan en niveles acumulados, gana aquella que haya subido en más
jugadores distintos. Un jugador cuenta una sola vez por temporada; si tuvo
varias ventas en ella, se conserva por habilidad su mayor aumento para no
duplicar el mismo tramo histórico.

Si todavía hay empate, se aplican estos desempates únicamente entre las
habilidades candidatas:

1. La habilidad del entrenamiento actual del equipo, leída del último
   `training.xml`.
2. La primera candidata según esta prioridad fija:

```text
Defensa → Portería → Jugadas → Anotación → Lateral → Pases → Balón parado
```

Si la temporada completa tiene cero niveles observados y cero jugadores con
alguna subida, queda `Sin evidencia suficiente`. El entrenamiento actual no se
usa en ese caso: no permite reconstruir lo que se entrenaba cuatro o cinco
temporadas atrás. El entrenamiento actual y la prioridad fija solo desempatan
habilidades respaldadas por al menos una subida observada en la temporada.

Se guardan la habilidad, los niveles que realmente aumentó esa habilidad y el
método (`Mayor aumento observado`, `Mayor suma de niveles en la temporada`,
`Empate en niveles · más jugadores`, `Empate · entrenamiento actual`, `Empate
· prioridad de habilidades` o `Sin evidencia suficiente`). El resultado se
recalcula después de cada sync: si llega evidencia de mayor prioridad, reemplaza
automáticamente el desempate anterior; si el desempate dependía del
entrenamiento actual, también puede cambiar cuando cambie ese entrenamiento.
El mismo backfill puede ejecutarse de nuevo de forma idempotente.

La ficha del exjugador, el detalle de Transferencias y la gráfica **Saldo por
entrenamiento en el momento de la venta** consumen esta asignación. No debe
confundirse con el tipo de entrenamiento general del club activo en la fecha de
venta, que se conserva como un dato histórico aparte.

## Pops e historial

Los pops de `trainingevents.xml` y los cambios entre snapshots son hechos
observados. Sirven para:

- mostrar el historial;
- contar semanas desde el último pop;
- contrastar diferencia entre semanas observadas y estimadas;
- detectar un posible error de implementación.

No actualizan, calibran ni reemplazan los coeficientes públicos.

## Límites visibles

- CHPP no publica el subnivel decimal.
- La edad histórica usada para contrastar un pop puede no ser la edad exacta
  de aquella semana si no existe el snapshot correspondiente.
- La tabla pública de edad termina en 34.
- Una proyección es una estimación, nunca un hecho futuro.

## Fuente

- Implementación pública: <https://github.com/ventouris/hattricktools/blob/master/static/js/training.js>
- Contexto general: <https://wiki.hattrick.org/wiki/Training>
