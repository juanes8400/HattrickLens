# 13 — Escalabilidad (millones de registros) y Estrategia Premium

## 1. Volumen esperado

Usuario activo ≈ 25 jugadores × ~2 snapshots/semana (con diffing) + 2 partidos + series económicas ≈ **~3.500 filas/año/usuario** en tablas grandes. 10.000 usuarios ⇒ ~35 M filas/año, dominadas por `player_snapshots` y `match_events`.

## 2. Estrategia de datos por etapas

**Etapa A (0-50 M filas, fases 1-4)** — PostgreSQL bien usado basta:
- Particionado RANGE mensual en snapshots (pruning en toda query con rango temporal).
- Diffing por `content_hash` (~-80% de filas), índices covering para las 10 queries top, `DISTINCT ON` + índice para "último snapshot".
- Read models materializados → el dashboard nunca escanea histórico.
- `pg_stat_statements` + presupuesto: ninguna query de UI >50 ms p95.

**Etapa B (50-500 M)**:
- Compresión de particiones frías (>12 meses) a tablas columnar-friendly o `pg_squeeze`; hot/cold: particiones viejas a tablespace en storage barato.
- Read replica para analytics/benchmark; PgBouncer; agregados pre-computados por temporada (rollups: 1 fila jugador-temporada) para charts largos — el detalle semanal solo se consulta al hacer zoom.
- Series temporales de charts servidas con downsampling LTTB en el query service.

**Etapa C (>500 M / analítica global)**:
- Envío de eventos a un almacén columnar (ClickHouse/DuckDB sobre Parquet en S3) para benchmark mundial y market trends; PostgreSQL queda como OLTP.
- Extracción del worker-compute a servicio propio si la CPU de simulaciones compite con la ingesta.

Reglas siempre: nunca `SELECT *` sobre particionadas; paginación por cursor; jobs de retención/rollup en Celery Beat; test de performance con dataset sintético de 100 M filas antes de cada etapa.

## 3. Preparación premium (diseñado desde F1, activado en F5)

| Capability | Diseño previo que lo habilita |
|---|---|
| **Suscripción (Stripe)** | `users.plan` + tabla `subscriptions`; todos los límites (equipos, syncs/día, runs de Monte Carlo, preguntas AI) leídos de `plan_limits` — nunca hardcodeados |
| **Comparativas avanzadas** (benchmark mundial, percentiles por división) | agregados anónimos globales separados de datos por-tenant desde el modelo de datos |
| **IA generativa** (informes semanales redactados, scouting narrativo) | AI Assistant ya es function-calling sobre motores; añadir plantillas de informe es incremental |
| **Análisis colaborativo** (compartir informes/read-only con la federación) | URLs firmadas con scope de recurso + `shared_views`; permisos por recurso ya en repositorios |
| **App móvil** | API REST completa + GraphQL (F5) + auth por token: el backend no asume browser; PWA primero, wrapper nativo después |
| **API pública para CHPP devs** | keys por app, mismos query services, rate limit por key — pero ojo: redistribuir datos HT requiere que el tercero sea CHPP aprobado |

### Palancas de monetización coherentes con el diseño
Free: 1 equipo, histórico 1 temporada, sync estándar, dashboard+plantilla+training básico.
Pro: multi-equipo, histórico ilimitado, simuladores, predicciones, AI Assistant, prioridad en colas de sync/compute, exports.
El coste marginal (CPU de simulación, almacenamiento histórico, LLM) coincide con las features de pago — el pricing protege los costes.
