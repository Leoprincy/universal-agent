# Development Roadmap

This roadmap formalizes the sequential eight-phase development model for Universal Autonomous Growth Agent (UGA), preserving the original domain boundaries, scope definitions, and phase exit principles.

## Completed and Active Phases

### Phase 1 — Project Foundation
- Establish the repository, backend, dashboard, local infrastructure, configuration, health reporting, documentation, and baseline checks.
- Keep PostgreSQL and Redis connectivity optional so the API can start before infrastructure is available.
- Establish core configuration and system info APIs.

### Phase 2 — Domain Model and Persistence
- Define products/projects, ownership, lifecycle rules, and SQLAlchemy domain models.
- Introduce reviewed Alembic database migrations.
- Support project persistence and database-level unique constraints.

### Phase 3 — Product Workspace
- Add CRUD APIs and dashboard flows for projects with authorization boundaries appropriate to the deployment model.
- Support slug generation, collision handling, pagination, and status filtering.
- Implement server-derived single-tenant identity and API key security guards.

### Phase 4 — Research Records and Growth Opportunities
- Define research source provenance (`observed_at`, `published_at`, `collected_at`, `created_at`), evidence preservation, and source-type-specific validation.
- Implement growth opportunities with four-part taxonomy (`problem_statement`, `hypothesis`, `proposed_mechanism`, `target_audience`).
- Enforce deterministic priority matrix (`p0_urgent`, `p1_high`, `p2_medium`, `p3_low`) and bounded confidence score (`0.00` to `1.00`).
- Implement opportunity review lifecycle state machine (`draft`, `in_review`, `approved`, `rejected`, `archived`) with mandatory explanatory reasons.
- Establish immutable append-only status history ledger with composite project-integrity foreign keys.
- Implement many-to-many opportunity/research associations with contextual linking notes.
- Provide comprehensive dashboard interfaces: Research Vault, Opportunities Board, Detail Drawer, Evidence Linker, and Transition Modal.

## Future Phases (Not Started)

### Phase 5 — Campaign Planning
- Introduce human-reviewed plans, growth goals, budgets, constraints, and approval states.
- Support channel strategy synthesis prior to any execution or live network interaction.

### Phase 6 — Execution Adapters
- Add opt-in provider integrations behind interfaces, with credential management, rate limits, audit trails, and safety controls.
- Maintain strict sandbox isolation for any third-party marketing, messaging, or ad channel.

### Phase 7 — Measurement and Learning
- Model events and outcomes, attribution limitations, and repeatable evaluation before any automated optimization.
- Distinguish correlation from causation; ground learning in observable metrics.

### Phase 8 — Background Tasks and Queue
- Choose a Redis-backed task library only after job lifecycle, retries, observability, and idempotency are specified.
- Support background task execution and job monitoring.

## Phase Exit Principles

- Each phase introduces a small domain boundary and tests its API contract.
- External services remain optional and configurable; self-hosted operation remains supported.
- Destructive or externally visible campaign actions require explicit product-level safeguards.
- Provider and model choices are made against a concrete use case rather than embedded in foundational modules.
