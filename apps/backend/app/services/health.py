import asyncio

from app.core.contracts import AsyncConnectivityCheck
from app.schemas.health import ComponentHealth, HealthResponse

HEALTH_CHECK_TIMEOUT_SECONDS = 2.5


class HealthService:
    def __init__(self, database: AsyncConnectivityCheck, redis: AsyncConnectivityCheck) -> None:
        self._database = database
        self._redis = redis

    async def get_health(self) -> HealthResponse:
        database, redis = await asyncio.gather(
            self._check_component(self._database, "Database"),
            self._check_component(self._redis, "Redis"),
        )
        all_connected = database.status == "connected" and redis.status == "connected"
        return HealthResponse(
            status="healthy" if all_connected else "degraded",
            database=database,
            redis=redis,
        )

    @staticmethod
    async def _check_component(
        component: AsyncConnectivityCheck, component_name: str
    ) -> ComponentHealth:
        try:
            return await asyncio.wait_for(component.check(), timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return ComponentHealth(
                status="unavailable", message=f"{component_name} health check timed out"
            )
