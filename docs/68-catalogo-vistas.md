# HT Lens — Catálogo de 68 vistas

Consolidación y renumeración de todo lo discutido, agrupado por área. Cada
entrada indica: **datos** (ficheros CHPP que cruza), **qué muestra / insight**,
**visualización** y **enlaces** (hacia/desde qué otras vistas).

Marcas: ✅ ya construido · 🔶 construido, se enriquece · ⭐ favorito.

**Principio de navegación — todo lo enlazable se enlaza.** El CHPP entrega
`PlayerID`, `MatchID`, `TeamID` en cada fichero, así que cada nombre, partido o
equipo es un enlace. Destinos: Ficha de jugador (1), Ficha de partido (2),
Ficha de equipo (3), Ficha de temporada (4). Restricción CHPP: de jugadores de
otros clubes se muestra estado actual, nunca histórico.

---

## 1 · Páginas eje (destinos de todos los enlaces)

**1. Ficha de jugador** ⭐ — `playerdetails` + snapshots + `trainingevents` +
`playerevents` + `matchlineup`. Hero card, barras de habilidad con sublevel,
personalidad, timeline de carrera, partidos jugados, pops confirmados, origen
(club madre/cantera). *Viz: página perfil.* *Enlaces: ← desde cualquier nombre;
→ sus partidos, su fichaje, su cantera.*

**2. Ficha de partido** — `matchdetails` + `matchlineup`. Marcador, ratings por
sector, posesión, eventos narrados, alineaciones, goleadores. *Viz: página
partido.* *Enlaces: ← desde cualquier partido; → cada jugador, ambos equipos,
la jornada.*

**3. Ficha de equipo/rival** — `leaguedetails` + partidos públicos + `arena_details`.
Identidad, forma reciente, tácticas usadas, estadio. *Viz: página equipo.*
*Enlaces: ← desde clasificación/calendario; → sus partidos contra ti.*

**4. Ficha de temporada** — todo por temporada. Resumen de liga, copa,
economía, pops, fichajes de esa campaña. *Viz: página resumen.* *Enlaces: → todo
lo de esa temporada.*

**5. Dashboard / Panel de salud del club** ⭐ — economía + `players` + `fans` +
`club` + `matchdetails`. Balance estructural, edad media, forma, humor de
afición, eficiencia de entrenamiento, carga de lesiones: cada uno un semáforo
con sparkline. *Viz: rejilla de KPIs con mini-tendencias.* *Enlaces: → a cada
módulo.*

---

## 2 · Partido y táctica

**6. Narrativa y diagnóstico de partido** ⭐ — `matchdetails` (356 tipos de
evento) + traducción oficial. Cada gol por su vía real, SE ganados/fallados,
cambios de posesión y su causa, táctica que funcionó → diagnóstico accionable.
*Viz: timeline de eventos + veredicto.* *Enlaces: → jugadores, rival.*

**7. Embudo de ocasiones por zona** — `matchdetails` (`NrOfChances…`). Ocasiones
izq/centro/der → tiros → goles. Dónde se mueren las jugadas. *Viz: funnel por
banda.*

**8. Anillo de posesión** — `matchdetails` posesión por mitad. *Viz: donut
doble (1ª/2ª parte).* Simple y bello.

**9. Mapa de goles por minuto** — `matchdetails` goleadores con minuto. Cuándo
marcas y encajas. *Viz: heatstrip 0–90'.*

**10. Rendimiento por rol y comportamiento** ⭐ — `matchlineup` (`RoleID`,
`Behaviour`, `RatingStars`). ¿Tu lateral rinde mejor ofensivo o defensivo?
*Viz: barras por rol.* *Enlaces: → jugador.*

**11. Estrellas del partido** — `matchlineup` `RatingStars`/`…EndOfMatch`.
*Viz: fila de estrellas por jugador.* Simple y bello. *Enlaces: → jugador.*

**12. Heatmap de sectores × partidos** — `matchdetails` ratings en el tiempo.
El punto débil crónico salta. *Viz: mapa de calor.*

**13. Sobre/bajo rendimiento** — `matchdetails` (eventos 814/815) + serie
HatStats. ¿Juegas mejor o peor de lo que deberías por plantilla? *Viz: medidor
divergente + serie.*

**14. Contribución goleadora** — `matchdetails` goleadores/asistencias. Cuota de
goles del equipo. *Viz: barras/treemap.* *Enlaces: → jugador.*

**15. Disciplina y suspensiones** — `playerdetails.Cards` + amonestaciones
`matchdetails`. Quién está a una tarjeta de perderse un partido. *Viz: semáforo
por jugador.* *Enlaces: → jugador.*

**16. Planificador de alineación con órdenes** — `matchorders` (comportamientos,
marcaje, lanzador, capitán, táctica) + optimizador. *Viz: campo + panel de
órdenes.* *Enlaces: → jugador.*

**17. Once ideal sobre el campo** — optimizador + `position_engine` + formación.
Cada jugador coloreado por su rating; huecos en rojo. *Viz: campo con heatmap
posicional.* *Enlaces: → jugador.*

**18. Especialistas por condición y clima** ⭐ — `matchdetails` SE + `players.Specialty`
+ `regiondetails` (clima de mañana). "Tu técnico sufre con lluvia — llueve el
sábado". *Viz: matriz especialidad×clima.* *Enlaces: → jugador.*

**19. Simulador táctico** — `matchdetails` ratings + tácticas + motor. What-if
de táctica/actitud. *Viz: comparador antes/después.*

---

## 3 · Jugadores y plantilla

**20. Tarjeta de jugador** — `playerdetails`. Cromo: avatar, especialidad,
top-3 skills, forma. *Viz: card.* Simple y bello. *Enlaces: → ficha jugador.*

**21. Barras de habilidad con sublevel** — `playerdetails` + traducción.
"excelente alto". *Viz: barras horizontales elegantes.*

**22. Radar evolutivo** — snapshots + `trainingevents`. Radar hoy vs hace una
temporada. *Viz: radar de dos capas.*

**23. Comparador de dos jugadores** — dos fichas. *Viz: radar + stats lado a
lado.* *Enlaces: ↔ fichas.*

**24. Química y personalidad del vestuario** ⭐ — `playerdetails` (carácter,
agresividad, honestidad, liderazgo, lealtad) + traducción. Capitán óptimo, a
quién vender sin dañar moral. *Viz: matriz de personalidades.* *Enlaces: →
jugador.*

**25. Frontera de eficiencia TSI/salario** — `players`. Quién está sobrepagado.
*Viz: scatter con frontera + cuadrantes.* *Enlaces: → jugador.*

**26. Curva de depreciación por edad** — `pricing_engine` × edad + curva de
edad pico. *Viz: scatter + curva + cuadrantes.* *Enlaces: → jugador.*

**27. Pirámide de edad y relevo generacional** — `players` por posición.
Posiciones que envejecen a la vez. *Viz: pirámide poblacional.*

**28. Profundidad por posición** — `players.PositionCode` + `position_engine`.
Huecos de plantilla. *Viz: depth chart.* *Enlaces: → jugador.*

**29. Termómetro de forma** — `PlayerForm` + etiqueta nominal. *Viz: gauge.*
Simple y bello.

**30. Curva de fatiga del equipo** — `StaminaSkill` + minutos `matchlineup`.
Quién aguanta 90'. *Viz: bullet por jugador + histograma.*

**31. Cronología del jugador** — `playerevents` + `trainingevents` + snapshots.
Carrera completa en el club. *Viz: timeline.* *Enlaces: → partidos.*

**32. Nube/mapa de especialidades → eventos** — `players.Specialty` +
`matchdetails` SE. "4 técnicos pero solo 1 genera SE". *Viz: chord/treemap.*

**33. Camisetas y dorsales** — `DressURI` + `PlayerNumber`. Roster visual.
*Viz: mural de camisetas.* Simple y bello. *Enlaces: → jugador.*

---

## 4 · Entrenamiento

**34. Fórmula de entrenamiento (procedencia)** ✅ — `club`+`training`+`stafflist`+
`trainingevents`. Cada término leído del CHPP, validado contra pops confirmados.
*Viz: fórmula + tarjetas de procedencia + tabla de validación.*

**35. Plan de entrenamiento a largo plazo** — motor (fórmula cerrada). "Si
entrenas pases 10 semanas, estos suben, en este orden". *Viz: gantt de pops.*
*Enlaces: → jugador.*

**36. Progreso hacia el próximo pop** — `training` + snapshots. *Viz: anillo por
jugador.* Simple y bello. *Enlaces: → jugador.*

**37. Curva de aprendizaje del entrenador** ⭐ — `trainingevents` + cambios de
staff (`stafflist`/`club`). ¿Entrena más lento tu entrenador nuevo? *Viz: línea
acumulada con anotaciones.*

**38. Química de formación** — `training` experiencia por formación (442, 550…).
Qué formación juegas mejor hoy. *Viz: barras + optimizador.*

**39. Coste por punto de habilidad** — `pricing` + `training`. Valor ganado por
semana por skill. *Viz: barras ROI.*

**40. Optimizador del cuerpo técnico** — `club` (7 niveles) + `stafflist`
(costes) + lesiones `matchdetails`. ¿Cada empleado se paga solo? *Viz: tabla
coste↔beneficio.*

---

## 5 · Mercado y economía

**41. Buscador de mercado con nuestro motor** ⭐ — `transfersearch` +
`position_engine`. "Central que mejore mi once por <5M". *Viz: ranking por
rendimiento en tu esquema.* *Enlaces: → jugador (estado actual).*

**42. Detector de gangas** — `transfersearch` + `pricing_engine`. Precio de
salida ≪ valoración. *Viz: scatter precio↔valor.* *Enlaces: → jugador.*

**43. Matriz de decisión de venta** ⭐ — `players` + `pricing` + `trainingevents`
+ `transfersteam`. Retén/lista/vende-ya, ordenable. *Viz: matriz-cuadrante.*
*Enlaces: → jugador.*

**44. Momento óptimo de venta** — `transfersteam` (historial) + `pricing` +
`currentbids`. "Tus ventas cierran a +8% sobre valoración; lista el jueves".
*Viz: distribución + recomendación.* *Enlaces: → jugador.*

**45. Línea de tiempo de fichajes** — `transfersteam`. Compras/ventas con precio.
*Viz: timeline horizontal.* *Enlaces: → jugador.*

**46. Sankey del dinero** ⭐ — `economy` + `transfersteam`. Entradas → salidas,
ventas como caudal propio. *Viz: Sankey.*

**47. Proyección de caja** 🔶 — `economy` + `timeseries`. Ya existe; se enriquece
con efecto de cambios de staff/estadio. *Viz: banda p10–p90.*

**48. Agenda de vencimientos** — `currentbids` + `youthplayerdetails` +
`challenges` + `worlddetails`. Todo lo que vence en un sitio. *Viz: lista
cronológica.* *Enlaces: → jugador/partido.*

---

## 6 · Liga y competición

**49. Bump chart de la liga** — `leaguefixtures` reconstruido. Carrera de
posiciones jornada a jornada. *Viz: bump/racing lines.* *Enlaces: → equipo.*

**50. Tú vs la liga (percentiles)** — `leaguedetails` + `matchdetails` +
`economy`. Tus métricas como percentil de tu serie. *Viz: barras bullet.*

**51. Momentum del equipo** — `matches` + `matchdetails` + `fans`. Índice único
de tendencia. *Viz: streamgraph.*

**52. Ascenso/descenso con reglas reales** — `leaguelevels` (plazas exactas) +
simulador. *Viz: distribución con umbrales reales.*

**53. Índice de dureza del calendario** — `leaguefixtures` + fuerza rival.
Dificultad de lo que queda. *Viz: barras por jornada.* *Enlaces: → equipo.*

**54. Historial de enfrentamientos H2H** — `matchesarchive` + `matchdetails`.
*Viz: timeline de resultados.* *Enlaces: → equipo, partido.*

**55. Scouting del próximo rival** — partidos públicos del rival. Forma,
tácticas, ocasiones por zona. *Viz: one-pager.* *Enlaces: → equipo.*

**56. Copa: seguimiento y proyección** — `cupmatches` + `CupLevel`. *Viz: bracket
+ probabilidad de ronda.* *Enlaces: → partido, equipo.*

**57. Distribución de posición final** ✅ — simulador Monte Carlo. *Viz: barras
de probabilidad.*

---

## 7 · Estadio, afición y entorno

**58. Presión: expectativa vs realidad** — `fans.FanSeasonExpectation` +
simulador. Gap expectativa↔posición proyectada. *Viz: gauge divergente.*

**59. Predicción de asistencia e ingresos** — `fans` (asientos + clima) +
`arena_details` + rival. Taquilla del próximo partido con banda. *Viz: barras de
pronóstico.*

**60. Retorno del estadio en el tiempo** — `arena_details` (`RebuiltDate`,
`ExpansionDate`) + `fans`. Ampliaciones vs asistencia. *Viz: línea con hitos.*

**61. Demanda por sector** ✅ — `arena_details` (aforo real). Demanda censurada
marcada. *Viz: barras por sector.*

**62. Reloj de la semana Hattrick** — `worlddetails` fechas. Entrenamiento,
partido, economía en un anillo. *Viz: reloj radial.* Simple y bello.

**63. Bandera y región** — `regiondetails` + `worlddetails`. Región, clima de
hoy y mañana. *Viz: cabecera de locale.* Simple y bello.

---

## 8 · Juveniles

**64. Ranking de canteranos por potencial** — `youthplayerlist` +
`youthplayerdetails` (techos reales). *Viz: cards rankeadas.* *Enlaces: → ficha
juvenil.*

**65. Ojeador juvenil** — `youthteamdetails` (scout, viajes, `PlayerTypeSearch`).
Optimizar a quién buscar y cuándo viajar. *Viz: panel de ojeo + agenda.*

**66. Techos y desarrollo juvenil** 🔶 — `youthplayerdetails`. Ya existe; se
enriquece con `IsMaxReached`/`MayUnlock` reales. *Viz: barras nivel↔techo.*

---

## 9 · Manager y club

**67. Pasaporte del club / Medallero** — `managercompendium` + `achievements` +
`arena_details`. Tarjeta compartible con identidad, honores y estadio. *Viz:
tarjeta + rejilla de insignias.*

**68. Perfil y progreso del manager** — `managercompendium` + `achievements`.
Gamificación, hitos, último login. *Viz: perfil con progreso.*

---

## Notas de honestidad (lo que NO podríamos afirmar)

- **Jugadores rivales**: solo estado actual, nunca histórico (regla CHPP). El
  scouting (55) y el mercado (41) trabajan con lo público y puntual.
- **Escala del entrenador**: 1–5 del CHPP ↔ 7/8 de la fórmula, provisional.
- **Muestras cortas**: conversión, asistencia y momentum se marcan como ruido
  hasta tener datos suficientes, como ya hace el resto del producto.
- **SkillID de trainingevents**: mapeo provisional hasta confirmarlo.
