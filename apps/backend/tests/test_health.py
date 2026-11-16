import asyncio
import time

from app.schemas.health import ComponentHealth
from app.services.health import HealthService


class ConnectedCheck:
    async def check(self) -> ComponentHealth:
        return ComponentHealth(status="connected", message="Connected")


class HangingCheck:
    async def check(self) -> ComponentHealth:
        await asyncio.Event().wait()
        raise AssertionError("Unreachable")


def test_health_service_bounds_an_unresponsive_component() -> None:
    started = time.monotonic()
    response = asyncio.run(HealthService(ConnectedCheck(), HangingCheck()).get_health())

    assert time.monotonic() - started < 3
    assert response.model_dump() == {
        "status": "degraded",
        "application": "running",
        "database": {"status": "connected", "message": "Connected"},
        "redis": {"status": "unavailable", "message": "Redis health check timed out"},
    }
