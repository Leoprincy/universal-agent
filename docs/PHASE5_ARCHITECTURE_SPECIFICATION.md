# Phase 5: Strategy & Goals Architecture Specification

## 1. Executive Summary

Phase 5 introduces strategic growth planning and goal management into the Universal Autonomous Growth Agent (UGA). It connects validated research and growth opportunities from Phase 4 into coherent, measurable strategic objectives with declarative budget envelopes, concrete time horizons, and measurable key results.

Phase 5 maintains strict operational safety:
- **No live execution:** Channel strategy and campaign plans are declarative specifications. Third-party execution adapters belong to Phase 6.
- **No financial transactions:** Budget envelopes are policy constraints and allocation limits, not automated payment authorizations or ad-spend triggers.
- **Human approval required:** Strategic plans require explicit review and approval before becoming active.
- **Project and workspace isolation:** Enforced via server-derived identity and composite foreign keys across all entities.

---

## 2. Entity Architecture & Data Model

### 2.1 GrowthStrategy (`growth_strategies`)
A strategic plan representing a focused growth vector over a specific time horizon.

- `id`: UUID string (PK, 36 chars)
- `project_id`: Foreign key to `projects.id` with `ON DELETE CASCADE`
- `slug`: Project-scoped unique slug (e.g., `q1-student-activation-overhaul`)
- `name`: Human-readable name (max 200 chars)
- `description`: Optional comprehensive summary
- `strategic_vision`: Core thesis and guiding strategic narrative (mandatory)
- `target_audience`: Demographic, behavioral, or firmographic cohort (mandatory)
- `strategic_constraints`: Limitations, compliance boundaries, brand guidelines
- `budget_envelope`: Maximum allocated budget ceiling (Numeric 12, 2; declarative only)
- `currency`: ISO-4217 3-letter currency code (default: `USD`, checked for length == 3)
- `time_horizon`: Planning horizon (e.g., `Q1_2027`, `90_days`, `annual`)
- `status`: Lifecycle state (`draft`, `in_review`, `approved`, `active`, `completed`, `archived`)
- `metadata_json`: Optional JSONB metadata payload
- `created_at`, `updated_at`: UTC timestamps

**Constraints & Indexes:**
- Unique `(id, project_id)`: `uq_growth_strategies_id_project`
- Unique `(project_id, slug)`: `uq_growth_strategies_project_slug`
- Check `ck_growth_strategies_status`: Valid status values
- Check `ck_growth_strategies_budget`: `budget_envelope IS NULL OR budget_envelope >= 0.00`
- Check `ck_growth_strategies_currency`: `length(currency) = 3`
- Indexes on `(project_id, status)` and `(project_id, time_horizon)`

### 2.2 StrategyGoal (`strategy_goals`)
A measurable objective or key result tied to a strategy plan.

- `id`: UUID string (PK, 36 chars)
- `project_id`: Project identifier
- `strategy_id`: Foreign key to strategy
- `name`: Goal name / objective title (max 200 chars)
- `description`: Optional detailed description
- `metric_name`: Metric identifier (e.g., `activation_rate_pct`, `quick_apply_submissions`)
- `metric_unit`: Unit of measurement (`percent`, `count`, `currency_usd`, `milliseconds`)
- `baseline_value`: Initial measured starting point (Numeric 14, 4)
- `current_value`: Current progress value (Numeric 14, 4)
- `target_value`: Desired final objective (Numeric 14, 4)
- `deadline`: Target completion timestamp
- `status`: `pending`, `on_track`, `at_risk`, `behind`, `achieved`, `abandoned`
- `metadata_json`: Optional JSONB metadata
- `created_at`, `updated_at`: UTC timestamps

**Constraints & Indexes:**
- Composite FK `(strategy_id, project_id) -> growth_strategies(id, project_id)` with `ON DELETE CASCADE`
- Unique `(id, project_id)`: `uq_strategy_goals_id_project`
- Check `ck_strategy_goals_status`: Valid status values
- Indexes on `(strategy_id, status)` and `(project_id, status)`

### 2.3 StrategyOpportunityAssociation (`strategy_opportunity_associations`)
Many-to-many junction connecting strategies to approved Phase 4 growth opportunities.

- `strategy_id`: Primary key component, references strategy
- `opportunity_id`: Primary key component, references opportunity
- `project_id`: Project identifier
- `strategic_rationale`: Contextual justification explaining why this opportunity is incorporated
- `created_at`: UTC timestamp

**Constraints & Indexes:**
- Composite FK `(strategy_id, project_id) -> growth_strategies(id, project_id)` with `ON DELETE CASCADE`
- Composite FK `(opportunity_id, project_id) -> growth_opportunities(id, project_id)` with `ON DELETE CASCADE`
- Primary key on `(strategy_id, opportunity_id)`

### 2.4 StrategyStatusHistory (`strategy_status_history`)
Immutable audit trail of strategy lifecycle transitions.

- `id`: UUID string (PK)
- `strategy_id`: Strategy identifier
- `project_id`: Project identifier
- `previous_status`: Prior status (null for initial creation)
- `new_status`: Transitioned status
- `reason`: Explanatory justification (mandatory for consequential transitions)
- `actor`: Server-derived authenticated identity
- `system_metadata_json`: Optional transition metadata
- `created_at`: UTC timestamp

**Constraints & Indexes:**
- Composite FK `(strategy_id, project_id) -> growth_strategies(id, project_id)` with `ON DELETE RESTRICT`
- Indexes on `(strategy_id, created_at)` and `(project_id, created_at)`

### 2.5 GoalMetricUpdate (`goal_metric_updates`)
Append-only log of metric progress updates for each goal.

- `id`: UUID string (PK)
- `goal_id`: Goal identifier
- `project_id`: Project identifier
- `previous_value`: Previous metric value
- `new_value`: Recorded new metric value
- `notes`: Check-in commentary or observation notes
- `actor`: Server-derived authenticated identity
- `created_at`: UTC timestamp

**Constraints & Indexes:**
- Composite FK `(goal_id, project_id) -> strategy_goals(id, project_id)` with `ON DELETE RESTRICT`
- Indexes on `(goal_id, created_at)` and `(project_id, created_at)`

---

## 3. Business Rules and Lifecycle State Machine

### 3.1 Strategy Lifecycle
```text
  [draft] ──(submit)──> [in_review] ──(approve)──> [approved] ──(activate)──> [active] ──(finish)──> [completed]
     │                      │                          │                         │                      │
     │                      └──(reject/revise)──┐      └──(demote/revise)──┐     └──(pause)──┐          │
     │                                          ▼                          ▼                 ▼          │
     │                                       [draft]                    [draft]          [in_review]    │
     │                                          ▲                          ▲                            │
     │                                          │                          │                            │
     └────────────────(archive)─────────────────┴──────────(reactivate)────┴────────────(archive)───────┘
                                                │
                                                ▼
                                            [archived]
```

**Allowed Transitions:**
- `draft` $\rightarrow$ `in_review`, `archived`
- `in_review` $\rightarrow$ `approved`, `draft` (return for revision), `archived`
- `approved` $\rightarrow$ `active`, `draft` (demote for revision), `archived`
- `active` $\rightarrow$ `completed`, `in_review` (pull back for adjustments), `archived`
- `completed` $\rightarrow$ `archived`
- `archived` $\rightarrow$ `draft` (reactivate)

**Consequential Transitions Requiring Mandatory Justification (min 10 characters):**
- Any return or demotion to `draft` (`in_review` $\rightarrow$ `draft`, `approved` $\rightarrow$ `draft`)
- Pausing active strategies (`active` $\rightarrow$ `in_review`)
- Reactivation from `archived` $\rightarrow$ `draft`
- Any transition to `archived`

### 3.2 Opportunity Association Rules & Revalidation
1. **Draft Phase:** A `draft` strategy may link opportunities currently in `in_review` or `approved`. Opportunities in `draft`, `rejected`, or `archived` are rejected.
2. **Review & Approval Gate:** When a strategy transitions to `in_review`, all linked opportunities are re-evaluated; any rejected or archived opportunity blocks submission.
3. **Approval & Activation Strict Requirement:** When a strategy transitions to `approved` or `active`, **every linked opportunity must be in `approved` status**. If any linked opportunity was subsequently modified, demoted, or rejected, the strategy transition is rejected with `UnprocessableEntityError`.
4. **Project Scope:** Cross-project opportunity links are impossible by composite foreign key.

### 3.3 Goal Metric Progress Calculations
Goals track progress from `baseline_value` toward `target_value`:
1. **Increasing Metrics** ($target > baseline$):
   - Progress percentage: $\frac{current - baseline}{target - baseline} \times 100$
   - Higher values represent improvement.
2. **Decreasing Metrics** ($target < baseline$, e.g., error rate, cost-per-acquisition, latency):
   - Progress percentage: $\frac{baseline - current}{baseline - target} \times 100$
   - Lower values represent improvement.
3. **Flat Metrics** ($target = baseline$):
   - Division-by-zero protection returns $100\%$ if $current \ge target$, else $0\%$.
4. **Atomic Updates:** Recording progress updates both the `current_value` on `strategy_goals` and inserts an immutable `goal_metric_updates` row in a single database transaction.

### 3.4 Deletion Safeguards
- **Draft Strategies:** A strategy in `draft` status that has never undergone lifecycle transitions (only the initial creation history record exists), has no goals, and has no associated opportunities may be deleted. The initial history row and strategy are removed together.
- **Audited / Connected Strategies:** If a strategy has undergone lifecycle transitions (`previous_status is not None`), contains goals, or has linked opportunities, deletion is blocked with `ConflictError` (`code="cannot_delete_active_strategy"`). The strategy must be archived instead.
- **Goals with History:** A goal that has recorded metric updates cannot be deleted; attempts raise `ConflictError` (`code="cannot_delete_goal_with_history"`).

---

## 4. Multi-Tenancy and Authorization

1. **Server-Derived Identity:** `actor` on history records and progress updates is extracted from `identity.owner`. Client-supplied user identities or audit actors are strictly ignored.
2. **Workspace Isolation:** Every database query filters by `project.owner == identity.owner`.
3. **Database-Level Protection:** Composite foreign keys `(strategy_id, project_id)` prevent any possibility of cross-project data association or history leakage.
