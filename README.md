# HT Lens

> **The Ultimate Analytics Platform for Hattrick.org**
>
> Turn data into trophies.

Analytics platform for competitive Hattrick managers, built on the official
CHPP API. It turns raw game data into decisions: who to train, who to sell,
which eleven to field, and how much money the club will have a year from now.

## Documentation

The specification comes first; everything else records what was built and why.

### Specification

| Document | Contents |
|---|---|
| [VISION](docs/spec/VISION.md) | Product vision |
| [ARCHITECTURE](docs/spec/ARCHITECTURE.md) | Components, layers, principles |
| [DATABASE](docs/spec/DATABASE.md) | Logical data model |
| [API](docs/spec/API.md) | REST surface |
| [CHPP](docs/spec/CHPP.md) | Integration and synchronisation |
| [UI_GUIDELINES](docs/spec/UI_GUIDELINES.md) | Interface and interaction rules |
| [ROADMAP](docs/spec/ROADMAP.md) | Versions 0.1 → 4.0 |
| **[CORRECTIONS](docs/spec/CORRECTIONS.md)** | **Where evidence contradicts the spec** |

Engines and modules: [POSITION_ENGINE](docs/spec/POSITION_ENGINE.md) ·
[TRAINING_ENGINE](docs/spec/TRAINING_ENGINE.md) ·
[EXPERIENCE_ENGINE](docs/spec/EXPERIENCE_ENGINE.md) ·
[TEAM_MODULE](docs/spec/TEAM_MODULE.md) ·
[MATCHES_MODULE](docs/spec/MATCHES_MODULE.md) ·
[LEAGUE_MODULE](docs/spec/LEAGUE_MODULE.md)

### Implementation and research

| Document | Contents |
|---|---|
| [01-arquitectura](docs/01-arquitectura.md) → [13](docs/13-escalabilidad-premium.md) | Detailed engineering design |
| [14-inventario-hattrick-control](docs/14-inventario-hattrick-control.md) | 53 Hattrick Control screens catalogued |
| [15-historias-usuario](docs/15-historias-usuario.md) | 91 user stories with acceptance criteria |
| [16-calibracion-y-supuestos](docs/16-calibracion-y-supuestos.md) | Where every number comes from |
| [17-desarrollo-local](docs/17-desarrollo-local.md) | Running backend/frontend by hand, common OAuth/proxy pitfalls |

## Engines

Business logic lives in `backend/app/domain/engines/`. Each engine is pure: no
database, no HTTP, no framework. Constants live in `backend/app/config/*.yaml`
so behaviour can change without a deploy.

| Engine | Responsibility |
|---|---|
| `position_engine` | 19 positions + captain and set piece taker |
| `training_engine` | Development speed, pop forecast, training comparison |
| `experience_engine` | Experience progress and captain recommendation |
| `lineup_optimizer` | Best eleven via optimal assignment (Hungarian) |
| `pricing_engine` | Player valuation, sell window, training ROI |
| `economy_engine` | 52-week cash projection |
| `timeseries` | Five forecasting models with automatic selection |
| `arena_engine` | Occupancy, censored demand, expansion payback |
| `academy_engine` | Youth potential, promotion deadline, academy ROI |
| `match_analysis` | Sector ratings, chance conversion, HatStats |
| `insights` | Actionable alerts |

## Stack

**Backend** FastAPI · SQLAlchemy 2 · PostgreSQL · Redis · Celery · Alembic
**Frontend** React · TypeScript · Vite · React Router · TanStack Query · ECharts · Tailwind

## Quick start

```bash
cp .env.example .env        # fill CHPP_CONSUMER_KEY / SECRET
docker compose up -d        # postgres, redis, api, workers, frontend
make migrate                # alembic upgrade head
open http://localhost:3000
```

## The rule that shapes the product

CHPP requires that data downloads for manager-assistant applications are
**initiated by the user**, performed **sequentially**, and that rival players
are **never tracked over time**. Synchronisation is therefore a button the
manager presses, not a background job. See
[CORRECTIONS](docs/spec/CORRECTIONS.md).

Required attribution: *This application uses information from the online game
service Hattrick.org. This use has been approved by the developers and copyright
owners of Hattrick.org, Extralives AB.*

## License

MIT

## Módulos

| Módulo | Pantalla | Endpoint | Motor |
|---|---|---|---|
| Dashboard | `/dashboard` | `GET /teams/{id}/dashboard` | — |
| Plantilla | `/team` | `GET /teams/{id}/squad` | position_engine |
| Posiciones | `/positions` | `GET /players/{id}/positions` | position_engine |
| Alineación | `/lineup` | `GET /teams/{id}/lineup` | lineup_optimizer (húngaro) |
| Entrenamiento | `/training` | `GET /teams/{id}/training/forecast` | training_engine |
| Juveniles | `/academy` | `GET /teams/{id}/academy` | academy_engine |
| Transferencias | `/transfers` | `GET /teams/{id}/valuations` | pricing_engine |
| Partidos | `/matches` | `GET /teams/{id}/matches` | match_analysis |
| Liga | `/league` | `GET /teams/{id}/league` | season_simulator |
| Economía | `/economy` | `GET /teams/{id}/economy` | economy_engine + timeseries |
| Estadio | `/arena` | `GET /teams/{id}/arena` | arena_engine |
| Alertas | `/insights` | `GET /teams/{id}/insights` | insights |
| Motor | `/engine` | `GET /teams/positions/calibration` | todos |

Cada motor lee sus constantes de `backend/app/config/*.yaml`. Ninguna regla de
negocio vive en un componente de React: el frontend transporta y presenta, y
todos los números vienen calculados del servidor.

## Qué declara el producto sobre sí mismo

Un principio recorre el código y se puede comprobar en los tests: **cuando un
número no se puede saber, se dice, en vez de rellenarlo con un valor que parece
una medida.**

- La calibración de experiencia usa el valor configurado mientras no haya
  suficientes subidas observadas, y reporta cuántas faltan.
- La proyección económica de series de tiempo no aparece hasta que hay serie
  que validar; hasta entonces manda la estructural y se explica por qué.
- La demanda del estadio se marca como censurada cuando un sector se agota, y
  si no hay desglose de aforo por sector el servicio se niega a evaluarla.
- Las tasas de conversión vienen con su tamaño de muestra y marcadas como
  fiables o no.
- El simulador de liga avisa cuando el encogimiento pesa más que la evidencia.
- Los precios de entrada distinguen los verificados de los que vienen de la
  especificación.
