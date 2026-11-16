# Docker infrastructure

The repository-root `docker-compose.yml` is the source of truth for local infrastructure. It starts PostgreSQL and Redis only, publishes both on loopback, persists their data in named volumes, and includes readiness checks.
