# Development Roadmap

This roadmap records direction only. Later phases require separate implementation instructions; the current deliverable stops at the project foundation.

## Phase 1 — Project foundation (current)

- Establish the repository, backend, dashboard, local infrastructure, configuration, health reporting, documentation, and baseline checks.
- Keep PostgreSQL and Redis connectivity optional so the API can start before infrastructure is available.
- No product, campaign, analytics, AI, or agent behavior is implemented.

## Future phases (not started)

1. **Domain model and persistence:** define products/projects, ownership, lifecycle rules, SQLAlchemy models, and the first reviewed Alembic migration.
2. **Product workspace:** add CRUD APIs and dashboard flows with authorization boundaries appropriate to the deployment model.
3. **Research and opportunity records:** define source provenance, evidence, confidence, and review workflows before integrating research providers.
4. **Campaign planning:** introduce human-reviewed plans, goals, budgets, constraints, and approval states.
5. **Execution adapters:** add opt-in provider integrations behind interfaces, with credential management, rate limits, audit trails, and safety controls.
6. **Measurement and learning:** model events and outcomes, attribution limitations, and repeatable evaluation before any automated optimization.
7. **Background work:** choose a Redis-backed task library only after job lifecycle, retries, observability, and idempotency are specified.

## Phase exit principles

- Each phase introduces a small domain boundary and tests its API contract.
- External services remain optional and configurable; self-hosted operation remains supported.
- Destructive or externally visible campaign actions require explicit product-level safeguards.
- Provider and model choices are made against a concrete use case rather than embedded in foundational modules.
