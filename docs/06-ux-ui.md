# 06 — Diseño UX/UI

## 1. Design system

Estética: **Linear × Vercel** — densa, sobria, rapidísima. Nada de skeuomorfismo futbolero.

### Tokens

```css
:root[data-theme=dark] {
  --bg: #0a0a0b; --bg-subtle: #111113; --bg-elevated: #17171a;
  --border: #26262b; --text: #ededef; --text-muted: #8b8b93;
  --accent: #4f7cff;            /* acciones */
  --positive: #2fbf71; --negative: #e5484d; --warning: #f5a524;
  --chart-1..8: paleta categórica accesible (OKLCH, contraste AA);
  --radius: 8px; --font: Inter, system-ui; --font-mono: JetBrains Mono;
}
```

- Densidad: filas de tabla 36 px; spacing base 4 px; tipografía 13-14 px en datos, números tabulares (`font-variant-numeric: tabular-nums`).
- Semántica de color estable en TODA la app: verde=mejora/ingreso, rojo=deterioro/gasto, azul=acción/predicción, ámbar=alerta.
- Niveles de skill HT (0-20+) siempre con doble codificación: número + barra con escala de color perceptual (accesibilidad daltonismo).
- Light mode con los mismos tokens invertidos; `prefers-color-scheme` por defecto.

### Layout global

```
┌──────┬──────────────────────────────────────────────┐
│      │ Topbar: breadcrumb · search(⌘K) · SyncButton │
│ Side │──────────────────────────────────────────────│
│ bar  │                                              │
│ 232px│               Contenido                      │
│      │                                              │
└──────┴──────────────────────────────────────────────┘
```

- Sidebar: selector de equipo (multi-team), navegación por módulos con iconos lucide, favoritos arriba, colapsable a 56 px.
- SyncButton: estado permanente (verde=sync reciente, ámbar=stale + "hace 2 d", spinner con progreso durante sync). Es el corazón del cumplimiento CHPP: el usuario siempre inicia el sync.
- Responsive: <1024 px sidebar → drawer; <768 px tablas → cards apiladas con columnas prioritarias; charts se relayoutan a 1 col.

## 2. Pantallas

### Dashboard (`/dashboard`)
Grid de widgets configurables (drag&drop, tamaños S/M/L). Set por defecto, en orden:

1. **Team Strength** (L): radar de sectores + tendencia 8 semanas.
2. **Season Outlook** (M): p(ascenso) p(descenso) posición esperada — barras de probabilidad + posición como distribución mini.
3. **Financial Health** (M): cash, delta semanal, sparkline 12 sem, forecast 10 sem.
4. **Training Progress** (M): jugador en foco, próximos pops con countdown de semanas.
5. **Injuries & Cards** (S): lista activa con ETA de recuperación.
6. **Next Match** (M): rival, power comparison, win prob.
7. **TSI / Form / Stamina Evolution** (M): multi-línea del equipo.
8. **Team Spirit · Confidence · Fan Mood · Sponsors** (S x4): gauges compactos.
9. **Arena** (S): ocupación media, ingreso por partido.
10. **Transfer Opportunities** (M): jugadores propios en ventana óptima de venta.

Cada widget: menú ⋯ (ir al módulo, configurar, quitar), skeleton propio, deep-link.

### Equipo (`/squad`)
- Tabla virtualizada: columnas configurables (skills, edad, TSI, salario, forma, specialty, valor estimado, pop ETA). Filtros persistentes, multi-sort, selección → barra de acciones (comparar, exportar CSV).
- Vistas alternas (tabs): **Tabla · Radar comparado · Mapa de posiciones · Distribución** (histograma de skills/edades, treemap salarial).
- Header con KPIs: edad media, salario total, TSI total, valor estimado de plantilla, huecos por posición.

### Jugador (`/players/[id]`)
- Header: nombre, edad HT (años.días), specialty, forma/stamina como chips, valor estimado ± banda, botones Comparar/Favorito.
- Tabs:
  - **Overview**: radar, skills con sub-nivel estimado (barra fraccional), salario, TSI, experiencia/liderazgo.
  - **Timeline**: eventos verticales (pops ▲, lesiones ✚, tarjetas ▪, transfers ⇄, partidos) con scroll infinito.
  - **Evolución**: TimeSeries por métrica seleccionable con anotaciones.
  - **Entrenamiento**: velocidad actual, expected pop date, qué pasa si cambia el training.
  - **Mercado**: precio esperado, comparables (transfer compare), fecha/edad óptima de venta, ROI si se vende ahora vs óptimo, curva de depreciación.
  - **Partidos**: apariciones, rating por partido (línea de estrellas).

### Entrenamiento (`/training`)
- Panel superior: config actual (tipo, intensidad, stamina share, entrenador, asistentes) + **Training Speed efectiva** por jugador entrenado.
- Tabla de entrenables: skill actual (con fracción estimada), semanas→pop, expected pop date, training value €/semana.
- **Simulador what-if** (`/training/simulator`): panel dual "actual vs escenario". Cambios: tipo de training, intensidad, stamina, entrenador (nivel/coste), asistentes, vender/añadir jugador (buscador). Output: proyección de skills a N semanas (líneas superpuestas), delta de training value, coste del cambio, break-even. Escenarios guardables y comparables (hasta 3 columnas).
- Historial: semanas pasadas con pops logrados (confeti sutil en pops nuevos post-sync 😉 — una sola vez).

### Economía (`/economy`)
- KPIs: cash, delta semanal, salarios, ingreso arena, sponsors.
- **Sankey** de flujo semanal (ingresos → gastos).
- **Forecast 52 semanas** (`/economy/forecast`): área con banda de confianza; supuestos editables en panel lateral (asistencia, posición esperada, ventas planificadas) → recálculo instantáneo; eventos marcados (día económico, derbis).
- Tabla semanal exportable.

### Transferencias (`/transfers`)
- **Valuador**: form de skills/edad/specialty → precio esperado + banda min/max + n comparables + gráfico scatter de comparables (precio vs TSI, hexbin si >500 puntos).
- **Mis jugadores**: over/underpriced respecto a mercado, ventana óptima.
- **Skill Trader**: reglas (comprar X skill a edad Y bajo precio Z) → oportunidades y ROI simulado.
- Market trends: series de precios por arquetipo.

### Academia (`/academy`)
- Tabla de juveniles: skills actuales/máx (revelado progresivo), potencial score, edad, semanas restantes de pull óptimo.
- Ficha juvenil: proyección de skills al ascender, edad óptima de ascenso, valor estimado adulto, ranking interno.
- Comparador y ranking histórico de la academia.

### Liga (`/league`)
- Tabla con power ranking (ELO) vs posición real; fortaleza por sectores de cada rival (solo datos de partido — cumplimiento CHPP).
- **Predicción**: matriz posición×equipo (heatmap de probabilidades tras Monte Carlo), p(campeón/ascenso/descenso) por equipo, puntos esperados.
- Head-to-head configurable.

### Partido (`/matches/[id]`)
- Header marcador + posesión por mitad + attitude/táctica detectada.
- **Grid de ratings por sector** (3×3 comparado, delta coloreado), estrellas por jugador.
- Timeline de eventos con iconografía; xG aproximado acumulado (línea por minuto derivada de eventos de ocasión).
- Win probability pre-partido vs resultado; "qué decidió el partido" (sector dominante).
- Heatmap de dominancia por sector.

### Predicciones (`/predictions`)
- Simulación de temporada: parámetros (nº runs, lesiones on/off, forma variable) → distribución de posiciones (violin/histograma), evolución de p(ascenso) semana a semana, tabla de escenarios.

### AI Assistant (`/assistant`)
- Chat con respuestas estructuradas: tarjetas con cifras + gráfico embebido + "cómo se calculó" (fuentes: qué datos y qué motor). Preguntas sugeridas por contexto. Historial por equipo.

### Onboarding
1. Registro → 2. "Conecta tu Hattrick" (explicación OAuth, qué NO podemos hacer: nunca vemos tu contraseña) → 3. Autorización CHPP → 4. Selección de equipo(s) → 5. **Primer sync con progreso gamificado** (checklist de files) → 6. Dashboard con tour de 5 pasos (spotlight).

Estados vacíos SIEMPRE accionables: sin datos → botón de sync; sin histórico → "vuelve tras 2 semanas de datos, mientras tanto…" con lo que sí se puede mostrar.

## 3. Accesibilidad
WCAG 2.1 AA: contraste verificado en tokens, focus visible, navegación completa por teclado, `aria` en charts (tabla de datos alternativa), `prefers-reduced-motion` desactiva animaciones de charts.
