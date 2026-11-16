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

Authentication:
- Optional in default self-hosted mode (uses default workspace owner).
- When `UGA_API_KEY` is configured in backend environment: requires `Authorization: Bearer <key>` or `X-API-Key: <key>`. Missing or invalid keys return HTTP 401 Unauthorized.
- Optional `X-Workspace-Owner` header can be used to scope requests to a specific workspace owner.

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
