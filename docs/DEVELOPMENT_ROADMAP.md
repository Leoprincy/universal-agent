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

### Phase 5 — Strategy & Goals (Completed)
- Introduce growth strategies with declarative budget envelopes, ISO-4217 currency validation, strategic vision, constraints, and time horizons.
- Implement measurable strategic goals and key results with baseline, current, and target metrics.
- Support direction-aware progress calculations for both increasing metrics and decreasing metrics (lower is better) with zero-division safeguards.
- Establish strategy lifecycle state machine (`draft`, `in_review`, `approved`, `active`, `completed`, `archived`) with mandatory explanation reasons for consequential transitions.
- Enforce opportunity status revalidation upon strategy review and approval (all linked opportunities must be approved).
- Maintain immutable append-only ledgers for strategy status history and goal metric progress updates with server-derived actor identity.
- Enforce project-level composite foreign keys across strategies, goals, history, updates, and opportunity associations.
- Provide comprehensive REST API endpoints and full test suite covering CRUD, transitions, associations, and multi-tenancy isolation.
- Provide dashboard interfaces: Strategy Canvas, Detail Drawer, Goal Editor, Goal Progress Tracker, Opportunity Linker, and Strategy Transition Modal.
- Database migration `e5b2c3d4e6f7` verified and applied to application database.

## Future Phases (Not Started)

### Phase 6 — Execution Adapters (Completed)
- Add opt-in provider integrations behind interfaces, with credential management, rate limits, audit trails, and safety controls.
- Maintain strict sandbox isolation for any third-party marketing, messaging, or ad channel.
- Implemented: provider registry with replaceable adapter protocol, write-only Fernet-encrypted credential storage (fails closed without `UGA_CREDENTIAL_ENCRYPTION_KEY`), approval-gated action lifecycle bound to immutable payload hashes with configurable TTL expiry, DB-locked shared rate limiting, single-execution guarantees, sandbox-only enforcement, and append-only event/call audit ledgers.
- Ships the built-in `sandbox` adapter only; real provider adapters are added behind the same interface when a concrete use case exists.

### Phase 7 — Measurement and Learning (Completed)
- Model events and outcomes, attribution limitations, and repeatable evaluation before any automated optimization.
- Distinguish correlation from causation; ground learning in observable metrics.
- Implemented: project-scoped experiments under strategies (optional goal link), append-only outcomes with supersession-based corrections, deterministic success-criteria evaluation (`succeeded`/`failed`/`inconclusive` — insufficient data is never success), append-only evaluation history, and candidate→validated/rejected learning records with verified evidence references. Validated learnings are exposed via `GET /learnings/validated` as the integration point for future recommendation workflows (no recommendation engine exists yet). Experiment lifecycle transitions are row-locked and fully audited; project deletion is blocked by all Phase 7 audit tables. Dashboard: Experiments and Learnings consoles.

### Phase 8 — Background Tasks and Queue
- Choose a Redis-backed task library only after job lifecycle, retries, observability, and idempotency are specified.
- Support background task execution and job monitoring.

## Phase Exit Principles

- Each phase introduces a small domain boundary and tests its API contract.
- External services remain optional and configurable; self-hosted operation remains supported.
- Destructive or externally visible campaign actions require explicit product-level safeguards.
- Provider and model choices are made against a concrete use case rather than embedded in foundational modules.
