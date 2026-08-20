# Próximo Partido: qué tenía y qué de eso cabe en Rivales

El módulo **Próximo Partido** (`/next-match`) se retiró el 2026-08-19. Este
documento existe para que nada de lo que hacía se pierda por olvido: la idea es
que lo que valga la pena reaparezca dentro de **Rivales / RivalID**, que ya es
la pantalla donde se estudia a un rival concreto.

Se retiró porque hacía dos cosas a la vez y ninguna entera: por un lado repetía
media ficha de rival (once probable, comparativa, ratings de sector) y por otro
intentaba ser un guion de decisión ("sincroniza, lee al rival, prueba tu once"),
que es navegación disfrazada de análisis.

La diferencia real con Rivales era **el foco**: Próximo Partido miraba UN
partido concreto, el que viene, y por eso podía hablar de la alineación ya
enviada, del clima de ese día y de la condición física de hoy. Rivales mira al
EQUIPO rival a lo largo de sus últimos partidos. Todo lo que sigue está
clasificado por si esa distinción se sostiene o no.

## 1. Lo que Rivales ya cubre (no hay nada que rescatar)

| Lo que tenía Próximo Partido | Dónde está hoy |
|---|---|
| Once probable del rival, con recurrencia por jugador | Rivales: "Once probable" dentro de la comparativa |
| Comparativa propio vs. rival (TSI, forma, experiencia) | Rivales: "Comparación de plantilla" |
| Ratings de sector del rival | Rivales: "Duelos por zona de la cancha", con los cuatro métodos |
| Muestra de partidos analizados del rival | Rivales: KPI "Partidos analizados", ahora con el reparto por competición |
| Enlace a la ficha completa del rival | Rivales ES la ficha |
| "Alcance del análisis" (notas de qué se ve y qué no) | Retirado a propósito el 2026-08-19, junto con el panel equivalente de Rivales |

## 2. Lo que se pierde y merece volver a Rivales/RivalID

Esto es lo que Rivales **no** tiene hoy y sí aportaba valor. En orden de lo que
más se echa en falta:

1. **Condición física del once probable rival**, con resistencia, forma y
   experiencia medias, y el desglose **por línea** (defensa, medio, ataque) más
   el conteo de jugadores con resistencia ≤ 5. Es lo único de la vista que
   miraba el ESTADO de hoy y no el historial, y es justo lo que decide si
   presionas por un lado o aguantas. Fuente: `players.xml` del rival, campos
   `StaminaSkill` y `PlayerForm`, que CHPP sí expone de un equipo ajeno.
2. **Tu alineación enviada para ese partido**, con táctica, actitud y los
   ratings que predice el propio Hattrick (`matchorders.xml` con
   `predictratings`). Esto es de UN partido, así que en Rivales solo tiene
   sentido si la ficha sabe que ese rival es tu próximo contrincante.
3. **Once recomendado propio contra ese rival**, del optimizador de alineación.
   Hoy vive en Alineación sin saber contra quién juegas.
4. **La cabecera del partido**: fecha, competición y si juegas en casa o fuera.
   En Rivales podría ser una tira superior que aparezca solo cuando ese rival
   es el próximo, con el clima ya integrado (ver `domain/engines/weather.py`).

## 3. Lo que no merece volver

- **"Secuencia para decidir la formación"** (los cuatro pasos: sincroniza, lee
  al rival, prueba tu once, decide). Es un índice de navegación, no análisis.
- **El panel de notas al pie** con el alcance del análisis: mismo criterio que
  se aplicó al resto de la app al podar los avisos.

## 4. Qué se borró exactamente

- `frontend/src/pages/NextMatchPage.tsx`
- La ruta `/next-match`, su entrada de menú y el hook `useNextMatchAnalysis`
- `backend/app/api/v1/endpoints/next_match.py` y su registro en el router
- `nextMatchAnalysis` en `services/api.ts` con sus tipos

Se conservan intactas las piezas compartidas que usaba, porque Rivales las
sigue usando: `fetch_rival_matches_and_lineups` (rivals.py), el optimizador de
alineación y el motor de posiciones.
