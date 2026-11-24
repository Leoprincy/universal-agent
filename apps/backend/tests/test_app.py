import asyncio

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


async def request_with_lifespan(path: str, settings: Settings | None = None):
    app = create_app(
        settings
        or Settings(_env_file=None, environment="test", database_url=None, redis_url=None)
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(path)
    return app, response


def test_application_starts_and_shuts_down_cleanly() -> None:
    app, response = asyncio.run(request_with_lifespan("/api/v1/system/info"))

    assert response.status_code == 200
    assert app.state.database.configured is False
    assert app.state.redis.configured is False


def test_health_endpoint_reports_unconfigured_services_truthfully() -> None:
    _, response = asyncio.run(request_with_lifespan("/api/v1/health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "application": "running",
        "database": {"status": "not_configured", "message": "Database URL is not configured"},
        "redis": {"status": "not_configured", "message": "Redis URL is not configured"},
        "queue": None,
    }


def test_system_info_contains_public_metadata_only() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        redis_url="redis://user:system-info-secret@localhost/0",
    )
    _, response = asyncio.run(request_with_lifespan("/api/v1/system/info", settings))

    assert response.status_code == 200
    assert "system-info-secret" not in response.text
    assert response.json() == {
        "name": "Universal Autonomous Growth Agent",
        "version": "0.1.0",
        "environment": "test",
    }
