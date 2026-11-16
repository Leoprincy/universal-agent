# Technology Stack

## Selected foundation

| Area | Choice | Role |
| --- | --- | --- |
| Runtime | Python 3.11+ | Backend runtime |
| API | FastAPI and Pydantic | Versioned HTTP endpoints and validated contracts |
| Persistence | SQLAlchemy 2.x and Alembic | Relational access and future schema migrations |
| Database | PostgreSQL 16 (local Docker image) | Durable relational storage |
| Cache/jobs foundation | Redis 7 (local Docker image) | Future ephemeral state and queue infrastructure; no worker yet |
| Dashboard | React 18, TypeScript, Vite | Typed browser application and build pipeline |
| Styles | Tailwind CSS 3 | Utility styling and responsive UI |
| Quality | Pytest, ESLint, TypeScript | Backend tests, linting, and static type checks |
| Local infrastructure | Docker Compose | Starts only PostgreSQL and Redis |

## Why these boundaries

FastAPI and Pydantic provide explicit request/response models. SQLAlchemy separates persistence operations from API handlers, while Alembic provides a migration path once a real domain schema is designed. React and TypeScript consume the versioned JSON API and can be deployed independently. Docker Compose provides a low-friction self-hosted development environment without requiring a cloud account or orchestration platform.

## Upgrade paths

- A database driver or relational database can be changed behind SQLAlchemy configuration and migrations, with compatibility checked at the schema/query layer.
- Redis access stays behind an adapter; a future task queue can be added or replaced without placing queue semantics in route handlers.
- A different frontend framework can consume the same `/api/v1` contracts.
- AI and research providers are deliberately absent. When needed, define provider-neutral input/output contracts in services and keep vendor SDKs in adapters.
- Docker images and versions are pinned at the major line for local reproducibility; update them deliberately with compatibility checks.

## Dependency policy

The project installs only the API, database driver, Redis client, frontend build/UI tools, migration tool, and test/lint tools. There are no model weights, browser automation packages, paid API dependencies, mandatory hosted services, microservices, or Kubernetes manifests in this foundation.
