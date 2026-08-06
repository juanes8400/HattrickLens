# 03 — Diseño de API

## 1. Convenciones

- Base: `/api/v1`. Versionado por path. OpenAPI 3.1 autogenerada por FastAPI en `/api/v1/openapi.json`; tipos TS del frontend generados con `openapi-typescript` en CI.
- JSON `camelCase` hacia fuera (Pydantic alias generator), `snake_case` interno.
- Errores RFC 9457 (problem+json): `{type, title, status, detail, traceId}`.
- Paginación por cursor (`?cursor=&limit=`) en colecciones grandes; `?fields=` para sparse fieldsets.
- Idempotencia en POSTs de sync/simulación vía `Idempotency-Key`.
- Auth: `Authorization: Bearer <JWT access>` (15 min) + refresh token httpOnly cookie (30 días, rotación). CSRF double-submit en mutaciones desde browser.
- Rate limit por usuario y por IP (Redis sliding window), headers `RateLimit-*`.

## 2. Endpoints

### Auth y cuenta
```
POST   /auth/register | /auth/login | /auth/refresh | /auth/logout
GET    /auth/chpp/connect            → redirect URL de authorize CHPP
GET    /auth/chpp/callback           → intercambia verifier, guarda tokens, detecta equipos
DELETE /auth/chpp                    → revoca y borra tokens
GET    /me           PATCH /me       → perfil, preferencias, plan
```

### Equipos y sync
```
GET    /teams                        → equipos vinculados del usuario
GET    /teams/{teamId}               → detalle + último sync
POST   /teams/{teamId}/sync          → encola sync (user-initiated; body: {files?: [...]})
GET    /syncs/{jobId}                → estado
GET    /syncs/{jobId}/events         → SSE de progreso
GET    /teams/{teamId}/dashboard     → payload completo del dashboard (read model)
```

### Plantilla y jugadores
```
GET    /teams/{teamId}/players                    → roster con último snapshot (+filtros, sort)
GET    /players/{playerId}                        → ficha completa
GET    /players/{playerId}/timeline               → eventos (pops, lesiones, transfers, partidos)
GET    /players/{playerId}/history?metric=tsi&from=&to=   → serie temporal (tsi|form|salary|skills|stamina)
GET    /players/{playerId}/forecast               → proyección de skills/valor
GET    /players/{playerId}/valuation              → precio esperado, banda, fecha/edad óptima de venta, ROI
POST   /players/compare                           → body: {playerIds[], metrics[]}
```

### Entrenamiento
```
GET    /teams/{teamId}/training                   → config actual + historial de semanas
GET    /teams/{teamId}/training/progress          → pops, velocidad, expected pop dates por jugador
POST   /teams/{teamId}/training/simulate          → what-if: {trainingType?, intensity?, staminaShare?, coachLevel?, assistants?, roster diff (add/remove players)} → proyección N semanas
GET    /teams/{teamId}/training/roi               → training value generado por semana/jugador
```

### Economía
```
GET    /teams/{teamId}/economy                    → snapshot actual + breakdown
GET    /teams/{teamId}/economy/history            → series semanales
GET    /teams/{teamId}/economy/forecast?weeks=52  → cash flow proyectado con supuestos editables
POST   /teams/{teamId}/economy/simulate           → what-if económico (venta/compra, ampliación arena, staff)
```

### Transferencias
```
GET    /market/estimate                           → query: skills, age, specialty, form → precio esperado + banda
GET    /players/{playerId}/market                 → valoración + comparables (transfer compare)
GET    /teams/{teamId}/transfers                  → historial propio
POST   /market/skill-trader/scan                  → oportunidades según reglas del usuario
```

### Academia
```
GET    /teams/{teamId}/youth                      → juveniles + snapshots
GET    /youth-players/{id}/projection             → potencial, edad óptima de ascenso
GET    /teams/{teamId}/youth/ranking              → ranking interno por potencial
```

### Liga, partidos, predicciones
```
GET    /series/{seriesId}                         → tabla, equipos, power ranking
GET    /series/{seriesId}/prediction              → posiciones esperadas, p(ascenso/descenso/campeón)
GET    /matches/{matchId}                         → ratings, eventos, posesión, xG aprox
GET    /matches/{matchId}/analysis                → comparación sectores, win prob, heatmap data
POST   /teams/{teamId}/simulations/season         → encola Monte Carlo (params) → jobId
GET    /simulations/{jobId}                       → resultado (distribuciones)
```

### AI Assistant y analytics
```
POST   /assistant/query                           → {question} → respuesta estructurada + fuentes de datos usadas
GET    /teams/{teamId}/insights                   → insights/alertas/anomalías generadas
GET    /teams/{teamId}/benchmark?scope=world|country|division
```

## 3. Contratos ejemplo

`GET /teams/42/dashboard` (extracto):

```json
{
  "syncedAt": "2026-07-19T20:14:03Z",
  "stale": false,
  "strength": {"overall": 74.2, "midfield": 81, "attack": 70, "defence": 72, "trend": "+1.8"},
  "finance": {"cash": 12450000, "weeklyDelta": 310000, "health": "good", "forecast10w": 15550000},
  "season": {"pPromotion": 0.41, "pRelegation": 0.02, "expectedPosition": 2.3, "expectedPoints": 51.4},
  "training": {"type": "playmaking", "nextPops": [{"playerId": 9, "skill": "playmaking", "etaWeeks": 2.1}]},
  "alerts": [{"kind": "injury", "playerId": 3, "detail": "…"}]
}
```

## 4. Asincronía

Operaciones costosas (sync, Monte Carlo, forecast masivo) devuelven `202 {jobId}` y se siguen por SSE o polling. Los jobs son idempotentes por `Idempotency-Key` + hash de parámetros.

## 5. GraphQL (futuro)

Se preparará con: (a) query services ya desacoplados del transporte, (b) DTOs Pydantic → tipos Strawberry casi 1:1, (c) dataloaders sobre los mismos repos. Se montará en `/graphql` junto a REST sin romper v1. Trigger: cuando la app móvil necesite queries compuestas flexibles (fase 5).
