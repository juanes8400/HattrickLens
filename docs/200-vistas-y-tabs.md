# HT Lens — vistas seleccionadas (de 200 → 169)

Catálogo depurado tras tu revisión. Se conservan los números originales para
trazabilidad (los descartados dejan hueco; ver apéndice). Comentarios tuyos
incorporados como **→ nota**. Vistas nuevas marcadas **(nueva)**.

Nada está construido todavía: todo es por hacer. Leyenda: ⭐ diferencial.

Principio de navegación: **todo lo enlazable enlaza**. Nombres → Jugador (tab 3),
partidos → Partido (tab 5), equipos → Rival (tab 7). El CHPP da los IDs.

Pestañas (14, el tab Agenda se eliminó):
1. Inicio (5) · 2. Plantilla (15) · 3. Jugador (21) · 4. Entrenamiento (14) ·
5. Partidos (21) · 6. Liga (17) · 7. Rivales (13) · 8. Copa (5) · 9. Mercado (10) ·
10. Economía (14) · 11. Estadio y afición (13) · 12. Juveniles (9) ·
13. Club y staff (5) · 14. Motor (8). **Total: 169.**

---

## Tab 1 · Inicio (5)

1. **Panel de salud del club** ⭐ — economía+players+fans+club+matchdetails → rejilla de semáforos con sparklines.
3. **Alertas accionables** — motor de reglas de negocio que se leen como si las dijera una IA. → nota: generar ~5000 alertas predefinidas, sin tokens; lo discutimos aparte en detalle.
6. **Próximo partido** — season_simulator → barras de probabilidad + resultado probable.
7. **Momentum del equipo** — matches+matchdetails+fans → streamgraph.
9. **Tú vs la liga (percentiles)** — leaguedetails+matchdetails+economy → barras bullet.

## Tab 2 · Plantilla (15)

11. **Tabla maestra** — players → DataTable ordenable/filtrable. → nota: **debe ser hermosa**.
12. **Mural de tarjetas** — playerdetails → cards.
14. **Profundidad por posición** — position_engine → depth chart. → nota: mejor posición **y segunda mejor posición**.
15. **Pirámide de edad** — players → pirámide poblacional.
16. **Mapa de mejor posición** — position_engine → heatmap jugador×posición.
17. **TSI y habilidades en el tiempo** — players snapshots → histograma de TSI **+ histograma por cada habilidad + línea de suma de TSI + línea de promedio de TSI + promedio por habilidad**, todo con **filtro por habilidad y por periodo**.
18. **Distribución de salarios** — players → histograma.
19. **Frontera TSI/salario** — players → scatter + frontera. → nota: **coloreado por mejor posición**.
20. **Termómetro de forma** — PlayerForm → gauges.
21. **Curva de fatiga** — stamina+minutos → bullet + histograma.
22. **Semáforo de lesiones** — injury_level → lista.
23. **Disciplina y suspensiones** — cards+bookings → semáforo.
24. **Química y personalidad** ⭐ — playerdetails personalidad → matriz.
25. **Mapa de especialidades** — Specialty → treemap.
26. **Liderazgo y capitanes** — leadership+experience → ranking.

## Tab 3 · Jugador (21)

*Hub por jugador — destino de todos los enlaces de nombre.*

*Identidad*
27. **Hero card** — playerdetails → cabecera.
28. **Barras de habilidad (sublevel)** — playerdetails+traducción → "excelente alto".
29. **Radar de habilidades** — playerdetails → radar.
30. **Perfil de personalidad** — agreeability/aggressiveness/honesty → chips nominales.
31. **Especialidad y su efecto** — Specialty → tarjeta explicativa.

*Desarrollo*
32. **Radar evolutivo** — snapshots+trainingevents → radar hoy vs antes.
33. **Cronología de carrera** — playerevents+trainingevents → timeline.
34. **Historial de pops** — trainingevents → línea escalonada.
35. **Progreso al próximo pop** — training+snapshot → anillo.
36. **Proyección de habilidad** — motor → línea proyectada.
201. **Subida de experiencia** (nueva) — experience_engine → 27 puntos por nivel (medido), **contador de partidos que faltan según competencia** (liga ×1, copa/clasificación ×2, amistoso ×0,1…), con **promedio y desviación estándar de los niveles que históricamente se han necesitado**. → nota: es el cálculo que discutimos.

*Rendimiento*
37. **Partidos y rating** — matchlineup → tabla + sparkline.
38. **Rendimiento por rol/comportamiento** ⭐ — matchlineup → barras.
39. **Estrellas por partido** — matchlineup → serie de estrellas.
40. **Goles y asistencias** — matchdetails → contadores.

*Valor*
41. **Valoración y rango** — pricing_engine → gauge.
42. **Curva de valor por edad** — pricing → línea.
43. **Momento óptimo de venta** — pricing+transfersteam → recomendación.
44. **ROI de entrenarlo** — pricing+training → barras.

*Contexto*
45. **Origen (club madre/cantera)** — MotherClub+former youth → tarjeta.
46. **Salario, TSI y lealtad** — playerdetails → mini-KPIs.

## Tab 4 · Entrenamiento (14)

47. **Fórmula con procedencia** ⭐ — club+training+stafflist+trainingevents → fórmula + tarjetas de fuente.
48. **Validación contra pops** — trainingevents → tabla observado vs predicho.
49. **Previsión de subidas** — motor → tabla ordenada por semanas.
50. **Progreso de cada jugador** — training+snapshots → rejilla de anillos.
51. **Plan a largo plazo** — motor → gantt de pops.
52. **Comparar tipos de entrenamiento** — motor → barras semanas/skill.
53. **Curva de aprendizaje del entrenador** ⭐ — trainingevents+staff → línea con anotaciones.
54. **Química de formación** — training experiencia por formación → barras.
55. **Minutos de entrenamiento** — matchlineup → barras por jugador.
56. **Reparto intensidad/condición** — training → donut.
57. **Moral y confianza** — training → dos gauges nominales.
58. **Coste por punto de habilidad** — pricing+training → barras ROI.
59. **Efecto del cuerpo técnico** — club+stafflist → tabla.
60. **Historial de tipo de entrenamiento** — training snapshots → timeline.

## Tab 5 · Partidos (21)

*Lista y forma*
61. **Historial de partidos** — matches → DataTable.
62. **Resultados** — matches → píldoras V/E/D. → nota: no se llama "Form Guide"; con **filtro por competencia y por fechas**.
63. **HatStats / Loddar** — matchdetails → línea. → nota: no vienen literales; se **calculan** de los ratings por sector (que sí están). Si un partido no trae ratings, no se muestra.
64. **Sobre/bajo rendimiento** — matchdetails → medidor divergente. → cómo (tu decisión): **solo cálculo propio** — desviación de tu HatStats de cada partido frente a tu media móvil, en σ. No se usan los eventos 814/815.

*Ficha de partido (hub de detalle)*
65. **Marcador y resumen** — matchdetails → cabecera.
66. **Histórico de ratings por sector** — matchdetails → líneas por sector. → nota: cambiado de "radar único" a **histórico con filtro de fechas y competencias**.
67. **Heatmap sectores × partidos** — matchdetails → heatmap.
68. **Anillo de oportunidades** — matchdetails → donut de ocasiones (izq/centro/der/SE/otras). → nota: reemplaza el anillo de posesión (redundante).
69. **Embudo de ocasiones por zona** — matchdetails → funnel.
70. **Mapa de goles por minuto** — matchdetails → heatstrip 0–90'.
71. **Narrativa de eventos** ⭐ — matchdetails (356 tipos) → timeline narrada.
72. **Diagnóstico accionable** ⭐ — matchdetails → veredicto.
73. **Alineación en el campo** — matchlineup → campo SVG.
74. **Estrellas de la alineación** — matchlineup → estrellas.
75. **Sustituciones y órdenes** — matchlineup+matchorders → timeline.
76. **Táctica y actitud** — matchdetails → tarjeta.
77. **Balón parado (indirectas)** — RatingIndirectSetPieces → barras.
78. **Tarjetas y lesiones del partido** — matchdetails → lista.

*Especiales por condición*
80. **Eventos especiales ganados/fallados** ⭐ — matchdetails SE → tabla.
81. **Especialistas por clima** ⭐ — SE+Specialty+regiondetails → matriz.
82. **Conversión: generación vs definición** — matchdetails → tarjetas con muestra.

## Tab 6 · Liga (17)

83. **Clasificación** — leaguedetails → tabla enlazable.
84. **Bump chart jornada a jornada** — leaguefixtures → bump.
85. **Calendario de la serie** — leaguefixtures → lista/calendario.
86. **Simulación de temporada** — season_simulator → distribución. → nota: **Poisson con prior bayesiano** (encogimiento hacia la media de la liga) — el modelo que ya diseñamos.
87. **Distribución de posición final** — simulador → barras.
88. **Pronóstico por equipo** — simulador → tabla.
89. **Ascenso/descenso reales** — leaguelevels → umbrales exactos.
90. **Dureza del calendario** — leaguefixtures+fuerza → barras por jornada.
91. **Fuerzas ataque/defensa de la liga** — matchdetails → scatter.
92. **Goles a favor/contra por equipo** — leaguedetails → barras divergentes.
93. **Racha de cada equipo** — matches → mini form guides.
94. **Evolución de puntos** — leaguefixtures → líneas.
95. **Próxima jornada** — leaguefixtures+simulador → tarjetas de probabilidad.
96. **Matriz de enfrentamientos** — leaguefixtures → matriz quién-vs-quién.
97. **Tú vs media de la liga** — leaguedetails+economy → percentiles.
98. **Mapa de la serie (regiones)** — leaguedetails+regiondetails → mapa.
202. **Promedio de habilidades visibles de la liga** (nueva) — matchlineup/leaguedetails (lo visible) → media de skills visibles (experiencia, etc.) de todos los equipos de la serie.

## Tab 7 · Rivales / Scouting (13)

99. **Ficha de equipo rival** — leaguedetails+partidos públicos → página.
100. **Scouting del próximo rival** ⭐ — partidos públicos → one-pager.
101. **Tácticas usadas por el rival** — matchdetails → frecuencias.
102. **Ocasiones por zona del rival** — matchdetails → funnel.
103. **Forma reciente del rival** — matches → form guide.
104. **H2H histórico** — matchesarchive → timeline.
105. **Comparativa agregada de plantilla** — leaguedetails → barras.
105b. **Histograma de TSI: tú vs próximo rival** (nueva · implementada en HT-Lens) — players (propio) + matchlineup/players (rival) → histograma agrupado por tramos de TSI, con KPIs (total, diferencia, favorito por TSI). Tu lado es real; el del rival es muestra de ejemplo hasta sincronizar su alineación. Respeta la regla CHPP: de rivales solo estado actual, nunca histórico. Nota honesta en la propia vista: el TSI correlaciona con el rendimiento pero no decide el partido (táctica, especialistas, localía).
106. **Fortalezas/debilidades por sector** — matchdetails → radar.
107. **Estadio del rival** — arena (público) → tarjeta.
108. **Dónde te hacen daño** — matchdetails propios vs rival → heatmap.
109. **Peligrosidad del rival** — simulador → índice.
110. **Historial contra esta serie** — matchesarchive → resumen.

## Tab 8 · Copa (5)

111. **Bracket de copa** — cupmatches → bracket.
112. **Proyección de ronda** — cupmatches+simulador → probabilidad. → cómo: próximo cruce con precisión; rondas profundas con rival de fuerza media, etiquetado como aproximación.
113. **Nivel de copa** — matchdetails CupLevel/CupLevelIndex → tarjeta.
114. **Historial de copa** — matchesarchive cup → timeline.
115. **Próximo rival de copa** — cupmatches → pronóstico. → cómo: rival y fecha de cupmatches; fuerza estimada de sus resultados públicos, alimentada al modelo de #86.

## Tab 9 · Mercado (10)

121. **Valoración de la plantilla** — pricing → tabla.
122. **Matriz de decisión de venta** ⭐ — players+pricing+trainingevents+transfersteam → matriz.
123. **Momento óptimo de venta** — transfersteam+pricing+currentbids → recomendación. → cómo: tu % histórico sobre valoración + patrones de deadline + forma + pujas; aviso de muestra corta.
124. **Pujas activas** — currentbids → lista con deadline.
125. **Línea de tiempo de fichajes** — transfersteam → timeline.
126. **P&L de fichajes** — transfersteam → barras beneficio/pérdida.
127. **Comparar candidato vs plantilla** — transfersearch (iniciado por usuario)+position_engine → radar.
128. **Precio esperado de venta** — pricing → gauge.
132. **Coste de reforzar una posición** — depth+transfersearch+pricing → estimación. → cómo: hueco del depth chart + candidatos que encajan + precio de lo listado ahora (estimación, búsqueda iniciada por el usuario).
134. **Comisión y neto de venta** — transfersteam → desglose.

## Tab 10 · Economía (14)

135. **Resumen económico** — economy → KPIs.
136. **Balance estructural** — economy → gauge.
137. **Sankey del dinero** ⭐ — economy+transfersteam → sankey.
138. **Proyección de caja** — economy+timeseries → banda. → nota: **método de series de tiempo**.
139. **Series económicas** — economy snapshots → líneas. → nota: **filtro por tipo de ingreso/gasto y por tiempo**.
141. **Detección de anomalías** — timeseries → serie con marcas. → **+ filtro de tiempo**.
142. **Desglose de ingresos** — economy → barras. → **+ filtro de tiempo**.
143. **Desglose de gastos** — economy → barras. → **+ filtro de tiempo**.
144. **Peso y evolución de salarios** — players+economy → área. → **+ filtro de tiempo**.
145. **Coste del cuerpo técnico** — stafflist+economy → barras. → **+ filtro de tiempo**.
146. **Ingresos por taquilla** — fans+economy → línea. → **+ filtro de tiempo**.
147. **Efecto de un fichaje en la caja** — economy+plan → proyección. → **+ filtro de tiempo**.
148. **Efecto de ampliar estadio** — arena+economy → proyección. → **+ filtro de tiempo**.
149. **Semanas hasta números rojos** — economy → contador. → **+ filtro de tiempo**.

## Tab 11 · Estadio y afición (13)

151. **Ocupación por sector** — arena_details → barras.
152. **Demanda censurada** — arena_details → marcas.
153. **Simulador de ampliación** — arena+economy → tabla payback.
154. **Ingresos perdidos por asientos vacíos** — arena → barras.
155. **Asistencia por partido** — fans → serie.
156. **Predicción de asistencia** ⭐ — fans+arena+clima+rival → pronóstico con banda.
158. **Humor de la afición** — fans → termómetro nominal.
159. **Presión: expectativa vs realidad** ⭐ — fans+simulador → gauge divergente.
160. **Expectativa de temporada** — fans → tarjeta nominal.
161. **Expectativa de partido** — fans → tarjeta nominal.
162. **Humor → asistencia** — fans+eventos 475/476 → correlación.
163. **Patrocinadores** — economy+traducción → nivel nominal.
164. **Clima de tu región** — regiondetails → cabecera hoy/mañana.

## Tab 12 · Juveniles (9)

165. **Plantilla juvenil** — youthplayerlist → tabla.
167. **Ficha de juvenil (hub)** — youthplayerdetails → página.
168. **Techos vs alcanzado** — youthplayerdetails → barras nivel↔techo.
170. **Plazo de promoción** — CanBePromotedIn → cuenta atrás.
173. **Liga juvenil** — youthleaguedetails → tabla.
174. **Calendario juvenil** — youthleaguefixtures → lista.
175. **ROI de la academia** — economy youth+transfersteam → neto.
176. **Promocionados/vendidos** — former youth → timeline.
178. **Recomendación promover/despedir** — academy_engine → consejo.

## Tab 13 · Club y staff (5)

182. **Pasaporte del club** — managercompendium+arena → tarjeta compartible.
183. **Medallero** — achievements → rejilla de insignias.
184. **Perfil del manager** — managercompendium → perfil.
185. **Progreso de logros** — achievements → barras de progreso.
187. **Entrenador: perfil y contrato** — stafflist → tarjeta.

## Tab 14 · Motor / Transparencia (8)

189. **Motor de posiciones (calibración)** — position_engine → métricas.
190. **Fórmula de entrenamiento (procedencia)** — training_context → tarjetas.
191. **Puntos de experiencia (medido)** — experience_engine → intervalo de confianza.
192. **Modelo de simulación de liga** — season_simulator → ficha.
193. **Modelo de valoración** — pricing → ficha.
194. **Modelo de series de tiempo** — timeseries → backtest.
195. **Registro de supuestos** — docs → tabla.
196. **Procedencia de datos** — syncs → qué fichero, cuándo.

---

## Apéndice · Descartadas (33)

2, 4, 5, 8, 10, 13, 79, 116, 117, 118, 119, 120, 129, 130, 131, 133, 140, 150,
157, 166, 169, 171, 172, 177, 179, 180, 181, 186, 188, 197, 198, 199, 200.

Motivos que diste: no automatizable (120), redundante (68→reemplazada),
no visible/no se puede (150, y datos ajenos), y prioridad baja (el resto).
El tab **Agenda** completo se eliminó (197–200).

## Pendiente de conversación aparte

- **#3 Alertas** — motor de ~5000 reglas de negocio presentadas como si fueran
  IA, sin consumir tokens. A diseñar en detalle (catálogo de condiciones →
  plantillas de mensaje con variables del club).


---

# Priorización wow × esfuerzo (169 aprobadas)

Todo por construir. **Impacto** (Alto/Medio/Bajo) × **esfuerzo** (Bajo/Medio/Alto).

- **💎 Joya** = mucho wow, barata → primero.
- **🎯 Prioritaria** = mucho wow, esfuerzo medio → núcleo del v1.
- **🏔️ Apuesta** = mucho wow, cara → planificar, valen la pena.
- **✨ Bonita fácil** = agradable y barata → relleno visual.
- **🔧 Media / · Relleno / 🕗 Después** = segundo plano.

## Recuento

- 🎯 Prioritaria: **28**
- 🏔️ Apuesta: **21**
- ✨ Bonita fácil: **34**
- 🔧 Media: **58**
- · Relleno fácil: **14**
- 🕗 Después: **14**

_Total: 169_


## 💎 Joyas

—


## 🎯 Prioritarias (núcleo del v1)

#9 Tú vs la liga (percentiles), #14 Profundidad + 2ª posición, #19 Frontera TSI/salario, #24 Química y personalidad, #27 Hero card (hub), #32 Radar evolutivo, #33 Cronología de carrera, #36 Proyección de habilidad, #201 Subida de experiencia (nueva), #38 Rendimiento por rol, #41 Valoración y rango, #43 Momento óptimo de venta, #48 Validación contra pops, #53 Curva del entrenador, #64 Sobre/bajo rendimiento, #67 Heatmap sectores×partidos, #69 Embudo de ocasiones, #73 Alineación en el campo, #84 Bump chart, #87 Distribución final, #90 Dureza del calendario, #123 Momento óptimo de venta, #137 Sankey del dinero, #147 Efecto fichaje en caja, #148 Efecto ampliar estadio, #159 Presión expectativa↔real, #167 Ficha de juvenil (hub), #175 ROI de la academia


## 🏔️ Apuestas (caras pero diferenciales)

#1 Panel de salud, #3 Alertas (motor de reglas), #6 Próximo partido, #7 Momentum, #16 Mapa de mejor posición, #47 Fórmula con procedencia, #51 Plan a largo plazo, #71 Narrativa de eventos, #72 Diagnóstico accionable, #80 SE ganados/fallados, #81 Especialistas por clima, #86 Simulación (Poisson bayes.), #99 Ficha de equipo rival, #100 Scouting del próximo rival, #108 Dónde te hacen daño, #122 Matriz de decisión de venta, #138 Proyección de caja (TS), #152 Demanda censurada, #153 Simulador de ampliación, #156 Predicción de asistencia, #190 Fórmula (procedencia)


## ✨ Bonitas fáciles (relleno visual barato)

#12 Mural de tarjetas, #15 Pirámide de edad, #20 Termómetro de forma, #22 Semáforo de lesiones, #25 Mapa de especialidades, #26 Liderazgo y capitanes, #28 Barras de habilidad sublevel, #29 Radar de habilidades, #30 Perfil de personalidad, #31 Especialidad y su efecto, #34 Historial de pops, #35 Progreso al próximo pop, #39 Estrellas por partido, #50 Progreso (anillos), #57 Moral y confianza, #61 Historial de partidos, #65 Marcador y resumen, #68 Anillo de oportunidades, #74 Estrellas de la alineación, #76 Táctica y actitud, #77 Balón parado, #83 Clasificación, #93 Racha de equipos, #103 Forma del rival, #124 Pujas activas, #128 Precio esperado de venta, #135 Resumen económico, #136 Balance estructural, #158 Humor de la afición, #160 Expectativa de temporada, #161 Expectativa de partido, #170 Plazo de promoción, #184 Perfil del manager, #195 Registro de supuestos


## Tabla completa

| # | Vista | Wow | Esfuerzo | Cuadrante |
|---|---|---|---|---|
| 1 | Panel de salud | Alto | Alto | 🏔️ Apuesta |
| 3 | Alertas (motor de reglas) | Alto | Alto | 🏔️ Apuesta |
| 6 | Próximo partido | Alto | Alto | 🏔️ Apuesta |
| 7 | Momentum | Alto | Alto | 🏔️ Apuesta |
| 9 | Tú vs la liga (percentiles) | Alto | Medio | 🎯 Prioritaria |
| 11 | Tabla maestra (hermosa) | Medio | Medio | 🔧 Media |
| 12 | Mural de tarjetas | Medio | Bajo | ✨ Bonita fácil |
| 14 | Profundidad + 2ª posición | Alto | Medio | 🎯 Prioritaria |
| 15 | Pirámide de edad | Medio | Bajo | ✨ Bonita fácil |
| 16 | Mapa de mejor posición | Alto | Alto | 🏔️ Apuesta |
| 17 | TSI y habilidades en el tiempo | Medio | Alto | 🕗 Después |
| 18 | Distribución de salarios | Bajo | Bajo | · Relleno fácil |
| 19 | Frontera TSI/salario | Alto | Medio | 🎯 Prioritaria |
| 20 | Termómetro de forma | Medio | Bajo | ✨ Bonita fácil |
| 21 | Curva de fatiga | Medio | Medio | 🔧 Media |
| 22 | Semáforo de lesiones | Medio | Bajo | ✨ Bonita fácil |
| 23 | Disciplina | Medio | Medio | 🔧 Media |
| 24 | Química y personalidad | Alto | Medio | 🎯 Prioritaria |
| 25 | Mapa de especialidades | Medio | Bajo | ✨ Bonita fácil |
| 26 | Liderazgo y capitanes | Medio | Bajo | ✨ Bonita fácil |
| 27 | Hero card (hub) | Alto | Medio | 🎯 Prioritaria |
| 28 | Barras de habilidad sublevel | Medio | Bajo | ✨ Bonita fácil |
| 29 | Radar de habilidades | Medio | Bajo | ✨ Bonita fácil |
| 30 | Perfil de personalidad | Medio | Bajo | ✨ Bonita fácil |
| 31 | Especialidad y su efecto | Medio | Bajo | ✨ Bonita fácil |
| 32 | Radar evolutivo | Alto | Medio | 🎯 Prioritaria |
| 33 | Cronología de carrera | Alto | Medio | 🎯 Prioritaria |
| 34 | Historial de pops | Medio | Bajo | ✨ Bonita fácil |
| 35 | Progreso al próximo pop | Medio | Bajo | ✨ Bonita fácil |
| 36 | Proyección de habilidad | Alto | Medio | 🎯 Prioritaria |
| 201 | Subida de experiencia (nueva) | Alto | Medio | 🎯 Prioritaria |
| 37 | Partidos y rating | Medio | Medio | 🔧 Media |
| 38 | Rendimiento por rol | Alto | Medio | 🎯 Prioritaria |
| 39 | Estrellas por partido | Medio | Bajo | ✨ Bonita fácil |
| 40 | Goles y asistencias | Medio | Medio | 🔧 Media |
| 41 | Valoración y rango | Alto | Medio | 🎯 Prioritaria |
| 42 | Curva de valor por edad | Medio | Medio | 🔧 Media |
| 43 | Momento óptimo de venta | Alto | Medio | 🎯 Prioritaria |
| 44 | ROI de entrenarlo | Medio | Medio | 🔧 Media |
| 45 | Origen (club madre) | Medio | Medio | 🔧 Media |
| 46 | Salario/TSI/lealtad | Bajo | Bajo | · Relleno fácil |
| 47 | Fórmula con procedencia | Alto | Alto | 🏔️ Apuesta |
| 48 | Validación contra pops | Alto | Medio | 🎯 Prioritaria |
| 49 | Previsión de subidas | Medio | Medio | 🔧 Media |
| 50 | Progreso (anillos) | Medio | Bajo | ✨ Bonita fácil |
| 51 | Plan a largo plazo | Alto | Alto | 🏔️ Apuesta |
| 52 | Comparar tipos entren. | Medio | Medio | 🔧 Media |
| 53 | Curva del entrenador | Alto | Medio | 🎯 Prioritaria |
| 54 | Química de formación | Medio | Medio | 🔧 Media |
| 55 | Minutos de entrenamiento | Medio | Medio | 🔧 Media |
| 56 | Reparto intensidad/cond. | Bajo | Bajo | · Relleno fácil |
| 57 | Moral y confianza | Medio | Bajo | ✨ Bonita fácil |
| 58 | Coste por punto | Medio | Medio | 🔧 Media |
| 59 | Efecto cuerpo técnico | Medio | Medio | 🔧 Media |
| 60 | Historial tipo entren. | Bajo | Bajo | · Relleno fácil |
| 61 | Historial de partidos | Medio | Bajo | ✨ Bonita fácil |
| 62 | Resultados (filtros) | Medio | Medio | 🔧 Media |
| 63 | HatStats/Loddar | Medio | Medio | 🔧 Media |
| 64 | Sobre/bajo rendimiento | Alto | Medio | 🎯 Prioritaria |
| 65 | Marcador y resumen | Medio | Bajo | ✨ Bonita fácil |
| 66 | Histórico ratings por sector | Medio | Medio | 🔧 Media |
| 67 | Heatmap sectores×partidos | Alto | Medio | 🎯 Prioritaria |
| 68 | Anillo de oportunidades | Medio | Bajo | ✨ Bonita fácil |
| 69 | Embudo de ocasiones | Alto | Medio | 🎯 Prioritaria |
| 70 | Goles por minuto | Medio | Medio | 🔧 Media |
| 71 | Narrativa de eventos | Alto | Alto | 🏔️ Apuesta |
| 72 | Diagnóstico accionable | Alto | Alto | 🏔️ Apuesta |
| 73 | Alineación en el campo | Alto | Medio | 🎯 Prioritaria |
| 74 | Estrellas de la alineación | Medio | Bajo | ✨ Bonita fácil |
| 75 | Sustituciones y órdenes | Medio | Medio | 🔧 Media |
| 76 | Táctica y actitud | Medio | Bajo | ✨ Bonita fácil |
| 77 | Balón parado | Medio | Bajo | ✨ Bonita fácil |
| 78 | Tarjetas y lesiones | Bajo | Bajo | · Relleno fácil |
| 80 | SE ganados/fallados | Alto | Alto | 🏔️ Apuesta |
| 81 | Especialistas por clima | Alto | Alto | 🏔️ Apuesta |
| 82 | Conversión gen/def | Medio | Medio | 🔧 Media |
| 83 | Clasificación | Medio | Bajo | ✨ Bonita fácil |
| 84 | Bump chart | Alto | Medio | 🎯 Prioritaria |
| 85 | Calendario de la serie | Bajo | Bajo | · Relleno fácil |
| 86 | Simulación (Poisson bayes.) | Alto | Alto | 🏔️ Apuesta |
| 87 | Distribución final | Alto | Medio | 🎯 Prioritaria |
| 88 | Pronóstico por equipo | Medio | Medio | 🔧 Media |
| 89 | Ascenso/descenso reales | Medio | Medio | 🔧 Media |
| 90 | Dureza del calendario | Alto | Medio | 🎯 Prioritaria |
| 91 | Fuerzas de la liga | Medio | Medio | 🔧 Media |
| 92 | GF/GC por equipo | Bajo | Bajo | · Relleno fácil |
| 93 | Racha de equipos | Medio | Bajo | ✨ Bonita fácil |
| 94 | Evolución de puntos | Medio | Medio | 🔧 Media |
| 95 | Próxima jornada | Medio | Medio | 🔧 Media |
| 96 | Matriz de enfrentamientos | Bajo | Medio | 🕗 Después |
| 97 | Tú vs media de la liga | Medio | Medio | 🔧 Media |
| 98 | Mapa de la serie | Medio | Alto | 🕗 Después |
| 202 | Prom. habilidades liga (nueva) | Medio | Medio | 🔧 Media |
| 99 | Ficha de equipo rival | Alto | Alto | 🏔️ Apuesta |
| 100 | Scouting del próximo rival | Alto | Alto | 🏔️ Apuesta |
| 101 | Tácticas del rival | Medio | Medio | 🔧 Media |
| 102 | Ocasiones por zona rival | Medio | Medio | 🔧 Media |
| 103 | Forma del rival | Medio | Bajo | ✨ Bonita fácil |
| 104 | H2H histórico | Medio | Medio | 🔧 Media |
| 105 | Comparativa de plantilla | Medio | Medio | 🔧 Media |
| 106 | Fortalezas/debilidades | Medio | Medio | 🔧 Media |
| 107 | Estadio del rival | Bajo | Bajo | · Relleno fácil |
| 108 | Dónde te hacen daño | Alto | Alto | 🏔️ Apuesta |
| 109 | Peligrosidad del rival | Medio | Medio | 🔧 Media |
| 110 | Historial contra la serie | Bajo | Medio | 🕗 Después |
| 111 | Bracket de copa | Medio | Medio | 🔧 Media |
| 112 | Proyección de ronda | Medio | Medio | 🔧 Media |
| 113 | Nivel de copa | Bajo | Bajo | · Relleno fácil |
| 114 | Historial de copa | Bajo | Bajo | · Relleno fácil |
| 115 | Próximo rival de copa | Medio | Medio | 🔧 Media |
| 121 | Valoración de plantilla | Medio | Alto | 🕗 Después |
| 122 | Matriz de decisión de venta | Alto | Alto | 🏔️ Apuesta |
| 123 | Momento óptimo de venta | Alto | Medio | 🎯 Prioritaria |
| 124 | Pujas activas | Medio | Bajo | ✨ Bonita fácil |
| 125 | Timeline de fichajes | Medio | Medio | 🔧 Media |
| 126 | P&L de fichajes | Medio | Medio | 🔧 Media |
| 127 | Comparar candidato | Medio | Medio | 🔧 Media |
| 128 | Precio esperado de venta | Medio | Bajo | ✨ Bonita fácil |
| 132 | Coste de reforzar | Medio | Alto | 🕗 Después |
| 134 | Comisión y neto | Bajo | Bajo | · Relleno fácil |
| 135 | Resumen económico | Medio | Bajo | ✨ Bonita fácil |
| 136 | Balance estructural | Medio | Bajo | ✨ Bonita fácil |
| 137 | Sankey del dinero | Alto | Medio | 🎯 Prioritaria |
| 138 | Proyección de caja (TS) | Alto | Alto | 🏔️ Apuesta |
| 139 | Series económicas (filtros) | Medio | Medio | 🔧 Media |
| 141 | Detección de anomalías | Medio | Medio | 🔧 Media |
| 142 | Desglose ingresos | Bajo | Medio | 🕗 Después |
| 143 | Desglose gastos | Bajo | Medio | 🕗 Después |
| 144 | Peso de salarios | Medio | Medio | 🔧 Media |
| 145 | Coste del staff | Bajo | Medio | 🕗 Después |
| 146 | Ingresos por taquilla | Medio | Medio | 🔧 Media |
| 147 | Efecto fichaje en caja | Alto | Medio | 🎯 Prioritaria |
| 148 | Efecto ampliar estadio | Alto | Medio | 🎯 Prioritaria |
| 149 | Semanas a números rojos | Medio | Medio | 🔧 Media |
| 151 | Ocupación por sector | Medio | Medio | 🔧 Media |
| 152 | Demanda censurada | Alto | Alto | 🏔️ Apuesta |
| 153 | Simulador de ampliación | Alto | Alto | 🏔️ Apuesta |
| 154 | Ingresos perdidos | Medio | Medio | 🔧 Media |
| 155 | Asistencia por partido | Medio | Medio | 🔧 Media |
| 156 | Predicción de asistencia | Alto | Alto | 🏔️ Apuesta |
| 158 | Humor de la afición | Medio | Bajo | ✨ Bonita fácil |
| 159 | Presión expectativa↔real | Alto | Medio | 🎯 Prioritaria |
| 160 | Expectativa de temporada | Medio | Bajo | ✨ Bonita fácil |
| 161 | Expectativa de partido | Medio | Bajo | ✨ Bonita fácil |
| 162 | Humor→asistencia | Medio | Alto | 🕗 Después |
| 163 | Patrocinadores | Bajo | Bajo | · Relleno fácil |
| 164 | Clima de tu región | Bajo | Bajo | · Relleno fácil |
| 165 | Plantilla juvenil | Medio | Medio | 🔧 Media |
| 167 | Ficha de juvenil (hub) | Alto | Medio | 🎯 Prioritaria |
| 168 | Techos vs alcanzado | Medio | Medio | 🔧 Media |
| 170 | Plazo de promoción | Medio | Bajo | ✨ Bonita fácil |
| 173 | Liga juvenil | Bajo | Medio | 🕗 Después |
| 174 | Calendario juvenil | Bajo | Medio | 🕗 Después |
| 175 | ROI de la academia | Alto | Medio | 🎯 Prioritaria |
| 176 | Promocionados/vendidos | Medio | Medio | 🔧 Media |
| 178 | Recomendación promover | Medio | Medio | 🔧 Media |
| 182 | Pasaporte del club | Medio | Medio | 🔧 Media |
| 183 | Medallero | Medio | Medio | 🔧 Media |
| 184 | Perfil del manager | Medio | Bajo | ✨ Bonita fácil |
| 185 | Progreso de logros | Bajo | Medio | 🕗 Después |
| 187 | Entrenador: perfil | Bajo | Bajo | · Relleno fácil |
| 189 | Motor de posiciones | Medio | Alto | 🕗 Después |
| 190 | Fórmula (procedencia) | Alto | Alto | 🏔️ Apuesta |
| 191 | Puntos de experiencia | Medio | Medio | 🔧 Media |
| 192 | Modelo de simulación | Medio | Medio | 🔧 Media |
| 193 | Modelo de valoración | Medio | Medio | 🔧 Media |
| 194 | Modelo de series | Medio | Medio | 🔧 Media |
| 195 | Registro de supuestos | Medio | Bajo | ✨ Bonita fácil |
| 196 | Procedencia de datos | Medio | Medio | 🔧 Media |
