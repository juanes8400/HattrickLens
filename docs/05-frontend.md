# 05 — Arquitectura Frontend

## 1. Stack y estructura

Next.js (App Router) + TypeScript estricto + TailwindCSS + shadcn/ui + React Query (server state) + Zustand (client state) + Recharts/D3 (visualización).

```
frontend/src/
├── app/
│   ├── (marketing)/            # landing, pricing — estático, ISR
│   ├── (auth)/login|register|chpp-callback/
│   └── (app)/                  # shell autenticado: sidebar + topbar
│       ├── dashboard/
│       ├── squad/              # equipo
│       ├── players/[id]/
│       ├── training/           # + /simulator
│       ├── economy/            # + /forecast
│       ├── transfers/          # + /skill-trader
│       ├── academy/
│       ├── league/
│       ├── matches/[id]/
│       ├── predictions/
│       ├── assistant/
│       └── settings/
├── components/
│   ├── ui/                     # shadcn generados
│   ├── charts/                 # wrappers: RadarChart, SkillBar, TimeSeries, Heatmap, Sankey, PositionMap, DistributionChart
│   ├── domain/                 # PlayerCard, SkillBadge, SpecialtyIcon, FormIndicator, InjuryBadge, MoneyDelta, PopCountdown, TeamCrest, MatchRatingGrid
│   └── layout/                 # AppSidebar, Topbar, CommandPalette, SyncButton, WidgetGrid
├── lib/
│   ├── api/                    # cliente generado desde OpenAPI + fetch wrapper
│   ├── queries/                # hooks React Query por dominio (usePlayers, useDashboard…)
│   ├── stores/                 # Zustand: ui-store (sidebar, theme), widget-store (layout dashboard), sim-store (borradores what-if)
│   ├── format/                 # dinero, edad HT (años.días), niveles de skill i18n
│   └── ht/                     # constantes Hattrick (skills, specialties, tácticas) tipadas
├── hooks/                      # useSyncProgress (SSE), useHotkeys, useMediaQuery
└── styles/
```

## 2. División server/client

- **RSC por defecto**: páginas y secciones de solo lectura se renderizan en servidor (dashboard shell, ficha jugador SSR con datos iniciales → LCP rápido y SEO en páginas públicas).
- **Client components** solo para: charts interactivos, simuladores, command palette, widget drag&drop.
- Datos iniciales por RSC se hidratan en React Query (`initialData`) → sin doble fetch.

## 3. Estado

| Tipo | Herramienta | Ejemplos |
|---|---|---|
| Server state | React Query | roster, dashboard, forecasts. `staleTime` 60 s, invalidación por SSE `SyncCompleted` |
| Client/UI | Zustand (persist en localStorage) | tema, layout de widgets, favoritos, filtros de tabla |
| Borradores what-if | Zustand slice por simulador | cambios no persistidos hasta "Run" |
| URL | searchParams | filtros compartibles (deep-linking a comparaciones) |

Optimistic updates solo en mutaciones de preferencias (favoritos, layout); las simulaciones son 202+polling, con skeletons de resultado.

## 4. Componentes de visualización (contratos)

Cada chart es un wrapper tipado que recibe datos ya modelados por el backend (el front no calcula dominio):

- `SkillRadar({player | teamAvg, compareWith?})` — Recharts radar.
- `TimeSeries({series[], metric, events?})` — línea con anotaciones de eventos (pops, lesiones) — Recharts + brush para zoom.
- `SectorHeatmap({matchRatings})` — grid 3x3 de sectores, D3 escala de color.
- `CashFlowSankey({inflows, outflows})` — D3-sankey.
- `PositionMap({players[]})` — campo SVG con jugadores posicionados por rol óptimo.
- `DistributionChart({histogram, markers})` — resultado Monte Carlo (posiciones finales).
- `AgePyramid`, `SalaryTreemap`, `TransferScatter` (precio vs TSI, hexbin al densificar).
- Violin/ridgeline (D3) solo en vistas analytics avanzadas — lazy-loaded.

Regla: bundle de D3 importado por módulos (`d3-scale`, `d3-shape`…), nunca `d3` completo; charts pesados detrás de `next/dynamic`.

## 5. Performance

- Virtualización con `@tanstack/react-virtual` en tablas de plantilla (100+ filas con 20 columnas), academia y mercado.
- `next/font` (Inter variable), imágenes `next/image`, prefetch de rutas del sidebar.
- Memoización: selectores Zustand atómicos; `useMemo` en transformaciones de series; charts envueltos en `React.memo`.
- Infinite scroll (cursor) en timeline y transfer history.
- Brotli via Traefik; Analyze bundle en CI con presupuesto (First Load JS < 180 kB por ruta).
- Code-splitting por módulo de producto — cada área es un chunk.

## 6. Interacción global

- **Command Palette (⌘K)**: navegar, buscar jugador por nombre, acciones ("sync now", "simular temporada", "comparar X vs Y"). Implementación `cmdk`.
- **Search global**: índice client-side del roster + rutas; server-side para históricos.
- **Atajos**: `g d` dashboard, `g t` training, `s` sync, `?` ayuda.
- **Widgets**: dashboard en grid `dnd-kit`, layout persistido por usuario (Zustand → API `/me/preferences`). Cada widget declara `minW/minH`, fuente de datos y skeleton.
- **Dark mode**: `next-themes`, tokens CSS variables (doc 06); charts leen los tokens → un solo tema fuente.
- **i18n**: `next-intl`, claves para niveles de skill de HT (es/en al inicio).
