# 09 — Estrategia de Testing

## Pirámide

| Nivel | Herramientas | Alcance | Objetivo |
|---|---|---|---|
| Unit (dominio) | pytest + hypothesis | Motores puros: training, pricing, predicción, diffing | ≥90% cobertura del dominio; property-based en fórmulas (monotonía: más edad ⇒ menos velocidad; precios ≥ 0) |
| Unit (frontend) | Vitest + Testing Library | componentes domain/, hooks, formatters | lógica de presentación crítica |
| Contract CHPP | pytest + fixtures XML reales grabadas | parsers por file/version | todo XML de fixture parsea; campos nuevos no rompen (warning) |
| Integración API | pytest + httpx + testcontainers (PG+Redis reales) | use cases end-to-end: sync con CHPP fake, endpoints con DB real | flujos críticos: OAuth callback, sync completo, dashboard |
| Integración workers | Celery eager + testcontainers | cadenas de sync, retries, idempotencia | sync parcial reanuda; no duplica snapshots |
| E2E | Playwright | onboarding→conectar CHPP (mock server)→primer sync→dashboard; simulador training; economía | 8-10 journeys en Chromium+WebKit, mobile viewport incluido |
| Carga | k6 | dashboard y sync bajo 500 usuarios concurrentes | p95 < 400 ms API; colas estables |
| Regresión de modelos | suite estadística | backtesting: predicciones vs resultados reales guardados | Brier score de p(win) y error de pricing no empeoran entre releases |

## Piezas clave

- **CHPP fake server**: FastAPI mínimo que sirve las fixtures XML con el dance OAuth simulado — usado en integración y E2E; permite simular errores, latencia y revocación.
- **Fábricas**: factory-boy para entidades; builders de escenarios ("equipo división IV con 3 entrenables").
- **Snapshots dorados**: para el training engine, casos con resultado conocido de la comunidad (jugador 17 años, playmaking excelente → semanas a pop esperadas) como tests de caracterización.
- **Datos**: ninguna prueba usa datos reales de usuarios.

## Calidad estática
- Python: ruff (lint+format), mypy `--strict` en domain/application, import-linter (hexagonal).
- TS: `strict: true`, eslint (typescript-eslint + tanstack-query plugin), prettier.
- Pre-commit hooks + CI obligatorio en PR (doc 10). Convención de commits: Conventional Commits → changelog automático.
