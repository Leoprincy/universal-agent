# Version 1 API Contracts

These examples document the current browser-facing response shape. FastAPI response models in `apps/backend/app/schemas/` are authoritative.

## `GET /api/v1/health`

The endpoint returns HTTP 200 when the application can answer the health request. The aggregate state reflects live dependency probes.

```json
{
  "status": "degraded",
  "application": "running",
  "database": { "status": "not_configured", "message": "Database URL is not configured" },
  "redis": { "status": "unavailable", "message": "Redis is not reachable" }
}
```

Component status is `connected`, `not_configured`, or `unavailable`. Aggregate status is `healthy` only when PostgreSQL and Redis both report `connected`.

## `GET /api/v1/system/info`

```json
{
  "name": "Universal Autonomous Growth Agent",
  "version": "0.1.0",
  "environment": "development"
}
```

This response deliberately excludes environment variables, connection strings, and credentials.

## `GET /api/v1/projects`

Returns the paginated list of growth projects in this workspace.

Authentication & Workspace Scoping:
- In default self-hosted mode (no `UGA_API_KEY` configured), requests access the server-configured workspace (`UGA_WORKSPACE_OWNER`, default `default`).
- When `UGA_API_KEY` is configured in backend environment: requires `Authorization: Bearer <key>` or `X-API-Key: <key>`. Missing or invalid keys return HTTP 401 Unauthorized.
- Workspace identity is server-derived exclusively from `UGA_WORKSPACE_OWNER`. Client-supplied headers or request body fields cannot select or override the workspace owner.

Query parameters:
- `limit` (optional integer, default `50`, maximum `200`): Maximum items to return.
- `offset` (optional integer, default `0`, minimum `0`): Number of items to skip.
- `status` (optional string): Filter by status (`active`, `paused`, `archived`).
- `category` (optional string): Filter by category (`mobile_app`, `web_app`, `saas`, `ecommerce`, `other`).

```json
{
  "items": [
    {
      "id": "7b8e1e72-1c23-4d56-8e9a-0b1c2d3e4f5a",
      "name": "Android Part-Time Jobs App",
      "slug": "android-part-time-jobs-app",
      "owner": "default",
      "description": "Mobile app connecting students with local part-time opportunities.",
      "category": "mobile_app",
      "status": "active",
      "target_audience": "University students and local retail/service businesses",
      "metadata": { "platform": "Android", "package_name": "com.parttime.jobs" },
      "created_at": "2026-11-16T12:00:00Z",
      "updated_at": "2026-11-16T12:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

## `POST /api/v1/projects`

Creates a new growth project. Returns HTTP 201 Created on success, or HTTP 409 Conflict if a project with the requested slug already exists.

Request body:
```json
{
  "name": "Android Part-Time Jobs App",
  "slug": "android-part-time-jobs-app",
  "description": "Mobile app connecting students with local part-time opportunities.",
  "category": "mobile_app",
  "target_audience": "University students and local retail/service businesses",
  "metadata": { "platform": "Android" }
}
```

## `GET /api/v1/projects/{id_or_slug}`

Returns a single growth project by UUID or unique slug. Returns HTTP 404 Not Found if missing or not belonging to the caller's workspace.

## `PATCH /api/v1/projects/{id_or_slug}`

Updates an existing growth project. All fields in request body are optional. Returns HTTP 200 OK with the updated record.

Request body example:
```json
{
  "name": "Android Part-Time Jobs Platform",
  "status": "paused",
  "category": "mobile_app",
  "description": "Updated platform description"
}
```

## `DELETE /api/v1/projects/{id_or_slug}`

Deletes a growth project. Returns HTTP 204 No Content.


## `GET /api/v1/projects/{project_id_or_slug}/research`

Returns the paginated list of research records for a growth project.

Query parameters:
- `source_type` (optional string): Filter by source type (`user_interview`, `app_review`, `competitor_analysis`, `analytics`, `market_report`, `manual_observation`).
- `limit` (optional integer, default `50`, maximum `200`): Maximum items to return.
- `offset` (optional integer, default `0`, minimum `0`): Number of items to skip.

## `POST /api/v1/projects/{project_id_or_slug}/research`

Creates a new research record with strict provenance tracking and source-type-specific validation.

Request body example:
```json
{
  "title": "Play Store checkout hang reports",
  "source_type": "app_review",
  "source_name": "Google Play Store",
  "source_quote": "App spins for 30 seconds when clicking Apply and often fails silently.",
  "observation_summary": "Substantial customer friction observed in job application submission loop.",
  "interpretation_notes": "Application payload timeout likely caused by unindexed student document lookups.",
  "evidence_data": { "rating": 1, "app_version": "2.4.1" },
  "observed_at": "2026-11-18T10:15:00Z",
  "published_at": "2026-11-18T10:20:00Z"
}
```

## `GET /api/v1/projects/{project_id_or_slug}/opportunities`

Returns the paginated list of growth opportunities for a project.

Query parameters:
- `status` (optional string): Filter by status (`draft`, `in_review`, `approved`, `rejected`, `archived`).
- `category` (optional string): Filter by category (`acquisition`, `activation`, `retention`, `referral`, `revenue`, `experimentation`).
- `priority` (optional string): Filter by priority (`p0_urgent`, `p1_high`, `p2_medium`, `p3_low`).

## `POST /api/v1/projects/{project_id_or_slug}/opportunities`

Creates a new growth opportunity following the 4-part taxonomy. The initial status is always `draft`, priority is deterministically computed from impact and effort, and an initial status history record is committed in the same database transaction.

Request body example:
```json
{
  "title": "One-Tap Resume Quick-Apply for High-Intent Students",
  "problem_statement": "Students take 5 minutes to submit applications.",
  "hypothesis": "If we allow students to pre-upload verified resumes and apply in one tap, application completion rates will increase by 25%.",
  "proposed_mechanism": "Cache verified profile payloads on client.",
  "target_audience": "University students applying to retail shifts",
  "category": "activation",
  "estimated_impact": "critical",
  "estimated_effort": "low",
  "confidence_score": 0.85
}
```

## `POST /api/v1/projects/{project_id_or_slug}/opportunities/{id_or_slug}/transition`

Executes a validated lifecycle transition and records an immutable entry in `opportunity_status_history`. Rejections and returns to draft require an explanatory reason of at least 10 characters.

Request body example:
```json
{
  "status": "rejected",
  "reason": "Technical dependency on third-party verification API exceeds latency budget for Q4."
}
```

## `GET /api/v1/projects/{project_id_or_slug}/opportunities/{id_or_slug}/history`

Returns the chronological immutable audit trail of all lifecycle status transitions for an opportunity.

## `POST /api/v1/projects/{project_id_or_slug}/opportunities/{id_or_slug}/research`

Associates one or more research records with an opportunity, along with individual contextual notes. Enforces project-level integrity.


## `GET /api/v1/projects/{project_id_or_slug}/strategies`

Returns the paginated list of growth strategies for a project.

Query parameters:
- `status` (optional string): Filter by status (`draft`, `in_review`, `approved`, `active`, `completed`, `archived`).
- `time_horizon` (optional string): Filter by planning horizon (e.g. `Q1_2027`, `90_days`).
- `limit` (optional integer, default `50`, maximum `200`): Maximum items to return.
- `offset` (optional integer, default `0`, minimum `0`): Number of items to skip.

## `POST /api/v1/projects/{project_id_or_slug}/strategies`

Creates a new growth strategy in `draft` status. Automatically records an initial history entry in the same database transaction.

Request body example:
```json
{
  "name": "Q1 Student Activation Overhaul",
  "strategic_vision": "Streamline first-session application flow to double activation rate across university campuses.",
  "target_audience": "University students on Android mobile devices",
  "strategic_constraints": "No paid channels; adhere strictly to student brand guidelines",
  "budget_envelope": 5000.00,
  "currency": "USD",
  "time_horizon": "Q1_2027"
}
```

## `GET /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}`

Returns a single growth strategy by UUID or unique project-scoped slug.

## `PATCH /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}`

Updates a growth strategy. Status cannot be modified via PATCH; status changes must use the `/transition` endpoint.

## `DELETE /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}`

Deletes an untransitioned draft growth strategy. Returns HTTP 204 No Content. Returns HTTP 409 Conflict if the strategy has undergone transitions, has active goals, or has linked opportunities.

## `POST /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/transition`

Executes a validated lifecycle transition and records an immutable entry in `strategy_status_history`. Reversals, demotions, and archivals require an explanatory reason of at least 10 characters. Revalidates all linked opportunities.

Request body example:
```json
{
  "status": "in_review",
  "reason": "Strategy finalized with Q1 targets and ready for executive review."
}
```

## `GET /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/history`

Returns the chronological immutable audit trail of lifecycle status transitions for a strategy.

## `GET /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals`

Returns the list of measurable key results/goals for a strategy.

Query parameters:
- `status` (optional string): Filter by goal status (`pending`, `on_track`, `at_risk`, `behind`, `achieved`, `abandoned`).

## `POST /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals`

Creates a measurable key result goal for a strategy.

Request body example:
```json
{
  "name": "Day 7 Student Retention Rate",
  "description": "Increase Day 7 retention from 15% to 30%",
  "metric_name": "d7_retention_pct",
  "metric_unit": "percent",
  "baseline_value": 15.0,
  "target_value": 30.0,
  "deadline": "2027-03-31T23:59:59Z"
}
```

## `GET /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals/{goal_id}`

Returns a goal including calculated progress percentage and metric direction (`is_increasing_metric`).

## `PATCH /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals/{goal_id}`

Updates goal configuration or status.

## `DELETE /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals/{goal_id}`

Deletes a goal. Returns HTTP 204 No Content. Returns HTTP 409 Conflict if metric progress updates have been recorded for the goal.

## `POST /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals/{goal_id}/progress`

Records an append-only progress check-in, atomically updating the goal's `current_value` and inserting an immutable `goal_metric_updates` record.

Request body example:
```json
{
  "new_value": 22.5,
  "notes": "Mid-quarter check-in following rollout of cached profile apply."
}
```

## `GET /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/goals/{goal_id}/progress`

Returns the chronological history of metric progress check-ins for a goal.

## `GET /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/opportunities`

Lists all Phase 4 growth opportunities associated with this strategy along with contextual strategic rationale.

## `POST /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/opportunities`

Associates one or more growth opportunities with the strategy. Enforces status validation rules and project-level integrity.

Request body example:
```json
{
  "items": [
    {
      "opportunity_id": "4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a",
      "strategic_rationale": "Directly addresses application completion friction."
    }
  ]
}
```

## `DELETE /api/v1/projects/{project_id_or_slug}/strategies/{strategy_id_or_slug}/opportunities/{opportunity_id}`

Unlinks an opportunity from a strategy. Returns HTTP 204 No Content.
