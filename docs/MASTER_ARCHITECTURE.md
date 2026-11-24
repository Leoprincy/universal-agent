# Master Architecture

## Purpose and boundaries

Universal Autonomous Growth Agent is intended to become a self-hosted platform that can support multiple products and, over time, research markets, identify growth opportunities, plan campaigns, acquire customers, measure outcomes, and learn from results. This repository implements only the local project foundation: an HTTP API, a status dashboard, and PostgreSQL/Redis development infrastructure.

No AI model, browser automation, campaign orchestration, product records, or job worker is installed or simulated. Phase 6 adds an `app/integrations` adapter layer: provider registry, encrypted credential codec, approval-gated action service, shared rate limiting, and append-only audit ledgers. Only the built-in `sandbox` adapter ships; real providers plug in behind the `IntegrationAdapter` protocol without touching orchestration. Phase 7 adds the measurement domain: `Experiment` (bounded hypothesis test under a strategy, optional goal link), append-only `ExperimentOutcome` (supersession-based corrections), append-only `ExperimentEvaluation` (deterministic success-criteria verdicts: succeeded/failed/inconclusive — insufficient evidence is never success), `ExperimentStatusHistory` (row-locked, monotonically sequenced audit), and `LearningRecord` (candidate→validated/rejected with verified evidence references). `GET /learnings/validated` is the service-level integration point for future recommendation workflows; no recommendation engine exists yet.

## Current shape

```text
React + TypeScript dashboard (Vite)
            │ HTTP / JSON, /api/v1
            ▼
FastAPI application
  ├── API routes → application services
  ├── Pydantic response contracts
  ├── centralized settings and logging
  └── infrastructure adapters
       ├── SQLAlchemy → PostgreSQL
       └── Redis client → Redis
```

The dashboard owns presentation and calls the API over a versioned JSON boundary. Route handlers are thin: health aggregation lives in `app/services/health.py`; connection details live behind database adapters. The backend defines asynchronous connectivity-check contracts so later implementations can replace a library or service without changing the API shape.

## Backend organization

- `app/api`: route registration, dependencies, and HTTP endpoints.
- `app/core`: environment configuration, logging, infrastructure protocols, and application errors.
- `app/database`: SQLAlchemy and Redis lifecycle adapters; migration support is initialized without a premature domain schema.
- `app/schemas`: validated public response models.
- `app/services`: application-level orchestration.
- `tests`: API, configuration, lifecycle, and opt-in infrastructure checks.

Configuration is centralized in `Settings`, loaded from `UGA_`-prefixed environment variables and the repository-root `.env` when present. Secret URLs are represented as `SecretStr` and are not returned by system information endpoints. The application creates and closes infrastructure clients inside FastAPI's lifespan. A health check performs live connectivity probes when a URL is configured; it never reports an unconfigured service as connected.

## Frontend organization

The dashboard is a single React application with typed API response contracts, a small HTTP client, and separate page views for Overview, Projects, Agent Activity, and Settings. Overview and Settings use backend health and system-info responses. Projects and Activity currently present explicit empty states because no domain data or mutation APIs exist yet.

The frontend can be replaced independently as long as it continues to use the versioned API contract. Shared response examples are documented in `shared/contracts/api-v1.md`.

## Data and infrastructure

PostgreSQL is the durable relational store and SQLAlchemy is the backend access layer. Alembic is included for future schema migrations; no domain tables or initial migrations are defined in this foundation. Redis is provisioned for future ephemeral coordination and background jobs, but no queue or worker is started. Docker Compose runs only these two local services, stores data in named volumes, binds published ports to loopback, and checks service readiness.

## Decisions that keep upgrades local

1. **Versioned HTTP boundary.** Routes live under `/api/v1`; future response changes can be managed without binding the browser directly to Python internals.
2. **Pydantic contracts.** External payloads are validated models, making schema changes explicit and allowing TypeScript clients or generated schemas to be introduced later.
3. **Infrastructure behind adapters.** Database and Redis connectivity are small replaceable components. A different SQL driver, cache, queue, or hosted endpoint can be introduced behind the same application-facing contracts.
4. **No provider-specific AI coupling.** The initial repository has no AI SDK or model. A future provider interface can be selected when a concrete use case and deployment constraints are known.
5. **Configuration outside source.** URLs, ports, CORS, and runtime mode come from environment configuration; the checked-in example is only a local template.
6. **Single deployable application.** The API and dashboard remain a modular monolith for now. Domain boundaries can be extracted later only when operational needs justify it.
7. **Redis is optional to the app process.** A missing Redis URL degrades health reporting without preventing the API from starting, keeping local development and future deployment choices flexible.

## Operational behavior

`GET /api/v1/health` returns HTTP 200 with `healthy` only when both configured infrastructure dependencies respond. Missing or unreachable dependencies produce `degraded`, with a per-component state of `not_configured` or `unavailable`. `GET /api/v1/system/info` returns only application name, version, and environment. Error responses use a common envelope, and unexpected server errors are logged without exposing exception contents to clients.
