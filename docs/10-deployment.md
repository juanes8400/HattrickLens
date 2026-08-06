# 10 — Deployment e Infraestructura

## Entornos
- **local**: docker-compose completo (PG, Redis, api, workers, beat, frontend, Traefik opcional).
- **staging**: VPS único, compose + Traefik, datos sintéticos, CHPP sandbox propio (fake server).
- **production**: 1-2 VPS (Hetzner/DO) con compose gestionado por CI; migración a k8s solo si métricas lo exigen (doc 13).

## Topología producción

```
Cloudflare (DNS, TLS edge, WAF, cache estáticos, rate limit L7)
  → Traefik v3 (TLS origin, routing, compress, ratelimit middleware)
      → frontend (Next.js standalone, 2 réplicas)
      → api (uvicorn, 2-4 réplicas)
  PostgreSQL 16 (volumen dedicado, pgBackRest → S3)
  Redis 7 (AOF)
  worker-sync ×2 · worker-compute ×2 · beat ×1 (singleton con lock)
```

- Imágenes multi-stage: backend `python:3.12-slim` (uv para deps), frontend `node:22-alpine` build → standalone output.
- Healthchecks: `/health` (liveness) y `/ready` (DB+Redis) en api; Celery ping; Traefik solo enruta a ready.
- Migraciones: `alembic upgrade head` como job previo al rollout; reglas: migraciones siempre backward-compatible (expand→migrate→contract) para deploy sin downtime.
- Rollout: `docker compose up -d` con `--no-deps` por servicio, api en rolling (2 réplicas); rollback = redeploy tag anterior (imágenes inmutables por SHA).

## CI/CD (GitHub Actions)

```
PR:      lint (ruff/eslint) → typecheck (mypy/tsc) → unit → contract → build imágenes
main:    + integración (testcontainers) → E2E (playwright, compose efímero)
         → push imágenes ghcr.io:sha → deploy staging → smoke tests
release: tag semver → deploy production (aprobación manual) → smoke → Sentry release
```

Secretos por environment de GitHub; OIDC para registry. Presupuesto de pipeline < 12 min en PR (caching agresivo de uv/pnpm/docker layers).

## Backups y DR
- PG: base semanal + incrementales diarios + WAL → S3 (retención 30 d). Restore ensayado.
- Redis: efímero por diseño (todo reconstruible), AOF solo para colas.
- DR: infra reproducible desde repo (compose + `infra/`); RTO objetivo 4 h fase 1.

## Cloudflare
- Cache estáticos `_next/static` (immutable), bypass en `/api`.
- WAF managed rules + bot fight; page rule de mantenimiento.
- Turnstile en registro/login.
