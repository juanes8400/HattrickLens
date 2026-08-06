# ARCHITECTURE

# HT Lens System Architecture

## Purpose

This document defines the high-level architecture of HT Lens, its components, responsibilities, communication patterns and design principles.

The primary goal is to build a scalable, maintainable, modular analytics platform for Hattrick.org using the official CHPP API.

---

# Architectural Principles

- Domain-Driven Design (DDD)
- Clean Architecture
- SOLID principles
- Documentation-first development
- Configuration over hardcoded values
- Stateless APIs
- Event-driven synchronization
- Testability by design

---

# High-Level Architecture

```text
                 +----------------------+
                 |   Hattrick CHPP API  |
                 +----------+-----------+
                            |
                     OAuth2 / CHPP
                            |
                Synchronization Service
                            |
                    Message Queue (Redis)
                            |
                  Background Workers
                            |
                   Business Engines
                            |
 Repository Layer / ORM (SQLAlchemy)
                            |
                      PostgreSQL
                            |
                      FastAPI Backend
                            |
                    REST / JSON API
                            |
            React + TypeScript Frontend
```

---

# Backend Components

## FastAPI

Responsibilities:

- Authentication
- REST API
- Validation
- Authorization
- Business orchestration
- Documentation (OpenAPI)

---

## Business Engines

All business rules live here.

Examples:

- Position Engine
- Training Engine
- Experience Engine
- Match Engine
- League Engine
- Economy Engine
- Stadium Engine
- Prediction Engine
- Simulation Engine

Each engine must be independent.

No engine may directly access UI code.

---

## Repository Layer

Responsible for:

- Database access
- ORM mapping
- Query optimization
- Transactions

Suggested ORM:

SQLAlchemy 2.x

---

## Background Workers

Responsibilities:

- CHPP synchronization
- Historical imports
- Scheduled recalculations
- Statistics generation
- Cache refresh

Suggested:

Celery + Redis

---

# Database

Primary database:

PostgreSQL

Reasons:

- Excellent analytical capabilities
- JSON support
- Full ACID compliance
- Mature ecosystem
- Powerful indexing

Historical data is never overwritten.

Every synchronization appends or updates historical snapshots.

---

# Frontend

Technology:

- React
- TypeScript
- Tailwind CSS
- TanStack Query
- React Router
- ECharts

Responsibilities:

- Visualization
- User interaction
- Dashboard rendering
- Charts
- Forms
- Filters

Business rules must not exist inside React components.

---

# Synchronization Layer

Synchronization follows this workflow:

1. User authenticates with CHPP.
2. Synchronization service requests data.
3. Raw responses are stored.
4. Business engines recalculate derived metrics.
5. Dashboards are refreshed.

Synchronization should be incremental whenever possible.

---

# Business Flow

```text
CHPP
 ↓
Raw Data
 ↓
Normalization
 ↓
Persistence
 ↓
Business Engines
 ↓
Calculated Metrics
 ↓
REST API
 ↓
Frontend
```

---

# Modular Organization

Suggested backend structure:

```text
backend/
    api/
    core/
    config/
    models/
    repositories/
    services/
    engines/
    workers/
    schemas/
    tests/
```

Suggested frontend structure:

```text
frontend/
    components/
    pages/
    layouts/
    hooks/
    services/
    charts/
    types/
    assets/
```

---

# Cross-Cutting Concerns

- Logging
- Error handling
- Configuration
- Monitoring
- Metrics
- Security
- Rate limiting
- Caching

---

# Security

- OAuth authentication through CHPP
- JWT session management
- HTTPS only
- Secure secrets management
- CSRF protection where applicable
- Input validation
- Audit logging

---

# Performance Goals

- Initial dashboard < 2 seconds
- API responses < 300 ms (cached)
- Synchronization scalable to thousands of users
- Heavy calculations executed asynchronously

---

# Extensibility

Every new feature should be implemented as either:

- A new module
- A new business engine
- A new visualization

Existing modules should require minimal modification.

---

# Future Architecture

The architecture is intentionally designed to support:

- Mobile applications
- Public API
- AI recommendation services
- Machine Learning pipelines
- Monte Carlo simulations
- Plugin ecosystem
- Multi-language interface

---

# Guiding Principle

HT Lens is not a monolithic statistics viewer.

It is a modular analytics platform whose business intelligence is encapsulated in reusable engines that transform raw CHPP data into actionable insights.
