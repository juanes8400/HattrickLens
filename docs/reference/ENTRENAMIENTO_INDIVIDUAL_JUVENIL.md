# Entrenamiento Individual juvenil: habilidades y probabilidades por puesto

**Fecha de revisión:** 2026-08-26  
**Ámbito:** Academia juvenil de Hattrick  
**Estado de la evidencia:** mecanismo oficial; porcentajes estimados por la comunidad.

## Conclusión operativa

Cuando se selecciona **Individual**, cada juvenil recibe entrenamiento en una
sola habilidad sorteada entre las que Hattrick considera útiles para la posición
en la que disputó más minutos. La tabla siguiente es la distribución comunitaria
más reciente encontrada y es la que debe tomarse como referencia para HT Lens.

| Posición | Portería | Defensa | Jugadas | Pases | Lateral | Anotación | Balón parado |
|---|---:|---:|---:|---:|---:|---:|---:|
| Portero | 40% | 42% | — | — | — | — | 18% |
| Defensa central | — | 37% | 27% | 26% | — | — | 10% |
| Defensa lateral | — | 32% | 18% | 17% | 23% | — | 10% |
| Mediocentro | — | 28% | 39% | 23% | — | — | 10% |
| Extremo | — | 15% | 20% | 21% | 34% | — | 10% |
| Delantero | — | — | — | 26% | 26% | 38% | 10% |

Cada fila suma 100%.

## Reglas del sorteo

1. Se sortea una sola habilidad por jugador y partido.
2. La distribución depende del puesto en el que el jugador actuó más minutos.
3. La orden individual —normal, ofensivo, defensivo, hacia lateral o hacia el
   centro— no modifica estas probabilidades.
4. El sorteo no excluye habilidades que ya alcanzaron su potencial. Si sale una
   habilidad ya completada, el entrenamiento se pierde; no se vuelve a sortear.
5. Todos los puestos tienen alguna probabilidad de Balón parado.
6. Un mediocentro no recibe Lateral ni Anotación mediante Individual.
7. Un delantero puede recibir Anotación, Lateral, Pases o Balón parado, pero no
   Jugadas ni Defensa.

## Entrenamiento no significa revelación garantizada

Estos porcentajes describen la probabilidad de que una habilidad sea escogida
para **entrenarse**. No son directamente la probabilidad de que el entrenador
revele esa habilidad en el informe.

```text
habilidad sorteada -> recibe entrenamiento -> puede producir una revelación
```

Como regla general de la academia:

- el entrenamiento primario puede revelar el nivel actual;
- el entrenamiento secundario puede revelar el potencial;
- el entrenador informa solamente una selección limitada de jugadores y
  habilidades, por lo que el sorteo no garantiza un comentario.

## Diferencia frente a la estimación histórica

Una guía comunitaria de 2011 usaba como ejemplo para el mediocentro:

```text
Jugadas 50% / Pases 20% / Defensa 20% / Balón parado 10%
```

Era una aproximación temprana, no una tabla oficial. La revisión comunitaria de
2023 usa `39% / 23% / 28% / 10%`, respectivamente. HT Lens debe conservar la
fecha y procedencia de la distribución para que pueda sustituirse si aparece una
investigación general más reciente.

## Implicaciones para HT Lens

- No usar `50%` como velocidad del entrenamiento Individual: ese número nació
  como una probabilidad aproximada de escoger la habilidad principal.
- No asignar una habilidad fija a cada puesto. El motor debe conservar toda la
  distribución probabilística de la fila correspondiente.
- Incluir Pases y Balón parado entre los resultados posibles cuando corresponda.
- Mostrar estos porcentajes como **estimación comunitaria**, nunca como regla
  oficial publicada por Hattrick.
- No ajustar ni recalibrar las probabilidades usando los datos privados del
  equipo del propietario.

## Pendiente de revisión

- Revisar qué debe recomendar HT Lens para los juveniles más destacados como
  **defensa lateral** cuando su combinación fuerte es **Lateral + Defensa**.
  Hay que determinar si Individual sigue siendo la mejor elección, si conviene
  priorizar una de esas dos habilidades con entrenamiento específico y cómo
  debe reflejarse esa decisión en la selección de entrenamiento y formación.
  No modificar el motor hasta sustentar la regla con una fuente general.

## Fuentes

- [Hattrick Press: Altyapıda Antrenman (2023)](https://www.hattrick.org/mk/Community/Press/?ArticleID=21287): revisión comunitaria que publica la tabla usada arriba y sus referencias a investigaciones del foro.
- [Declaraciones de Hattrick sobre la academia juvenil](https://wiki.hattrick.org/wiki/HTs_on_Global/Youth_Academy): confirma que Individual sortea una habilidad valiosa para el puesto y que las habilidades más importantes tienen mayor probabilidad.
- [Manual oficial de Hattrick](https://wiki.hattrick.org/wiki/Manual): define Individual como entrenamiento de habilidades valiosas para la posición jugada.
- [Hattrick Press: The Youth Academy - Part 2 (2011)](https://www.hattrick.org/en/Community/Press/?ArticleID=13532): contiene la estimación histórica `50/20/20/10` para un mediocentro.
- [Manual no Escrito](https://wiki.hattrick.org/wiki/Manual_no_Escrito): enlaza los estudios del foro sobre probabilidades fijas por posición.

---

# Anexo: el estudio original (hilo 17350846)

**Capturado:** 2026-08-26 · **Fuente:** [`[Facts] YA training forms`](https://www86.hattrick.org/Forum/Read.aspx?t=17350846), de **glynzales**, 2020-07-16 (hilo cerrado; enlazado desde el Manual no Escrito por LA-Alpa).

Es el estudio del que sale la tabla de arriba. Aporta dos cosas que faltaban.

## 1. El ritmo NO es un número: es uno por habilidad

Post #13, «Training amounts from individual training (version July 13, 2020)»:

| Habilidad | Ritmo | Margen |
|---|---:|---|
| Pases | ~100 % | ±1 % |
| Defensa **(portero)** | ~82 % | ±10 %, **una sola observación** |
| Defensa | ~68,5 % | ±1 % |
| Jugadas | ~56,5 % | ±1 % |
| Lateral | ~42,5 % | ±5 % |
| Anotación | ~40 % | ±1 % |
| Balón parado | ~100 % | **conjetura declarada** |
| Portería | desconocido | el autor pone `?` |

Aquí está el «también es lento»: Anotación entrena al 40 % y Lateral al 42,5 %.
Un único porcentaje de velocidad para todo Individual es incorrecto.

## 2. Ejemplo resuelto que sirve de prueba independiente

Post #13, Defensa de principal e Individual de secundario, para un **defensa central**:

```
37 %  ->  146 % defensa
27 %  ->  100 % defensa + 38 % jugadas
26 %  ->  100 % defensa + 67 % pases
10 %  ->  100 % defensa + 67 % balón parado

media por partido: 117 % def + 17 % pas + 10 % jug + 7 % bp = 151 %
```

El modelo `probabilidad × ritmo × 2/3` reproduce las ocho cifras exactamente.
Está fijado en `tests/test_decision_individual.py` — si alguien toca la tabla o
los ritmos, esa prueba lo caza contra una fuente ajena a nosotros.

## 3. Otras constantes que confirma

- **Entrenamiento secundario = 66,7 %** (2/3), no el 50 % que decían las guías
  viejas. Es el valor que HT Lens ya usaba (`SECUNDARIO_NORMAL`).
- Entrenamiento doble 133,3 % · Amistoso 50 % · Pérdida por edad ~0,275 %/semana.

## 4. Advertencia del propio autor

Sobre la tabla de probabilidades escribe, en mayúsculas:

> «THIS TABLE IS BASED ON OLD STUDIES, and should not be seen as facts»

Y sobre el sorteo, lo que más importa para la academia:

> el jugador recibe entrenamiento en **una sola** habilidad por partido, elegida
> **con independencia de si esa habilidad ya alcanzó su potencial** — si sale una
> ya completada, el entrenamiento se pierde y no se vuelve a sortear.
