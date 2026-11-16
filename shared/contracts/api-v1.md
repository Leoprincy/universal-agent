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
