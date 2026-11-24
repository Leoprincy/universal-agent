import asyncio

from app.core.contracts import AsyncConnectivityCheck
from app.schemas.health import ComponentHealth, HealthResponse

HEALTH_CHECK_TIMEOUT_SECONDS = 2.5


class HealthService:
    def __init__(
        self,
        database: AsyncConnectivityCheck,
        redis: AsyncConnectivityCheck,
        queue: AsyncConnectivityCheck | None = None,
    ) -> None:
        self._database = database
        self._redis = redis
        self._queue = queue

    async def get_health(self) -> HealthResponse:
        checks = [
            self._check_component(self._database, "Database"),
            self._check_component(self._redis, "Redis"),
        ]
        if self._queue is not None:
            checks.append(self._check_component(self._queue, "Job queue"))
        results = await asyncio.gather(*checks)
        database, redis = results[0], results[1]
        queue = results[2] if self._queue is not None else None
        # Queue connectivity reflects Redis reachability plus depth readability;
        # worker availability is reported separately and never implied healthy.
        all_connected = database.status == "connected" and redis.status == "connected"
        return HealthResponse(
            status="healthy" if all_connected else "degraded",
            database=database,
            redis=redis,
            queue=queue,
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
