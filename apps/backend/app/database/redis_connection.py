import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.schemas.health import ComponentHealth

logger = logging.getLogger(__name__)


class RedisConnection:
    """Owns an async Redis client while keeping Redis replaceable at the service boundary."""

    def __init__(self, redis_url: str | None) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True) if redis_url else None

    @property
    def configured(self) -> bool:
        return self._client is not None

    @property
    def client(self):
        """Expose the async client for queue adapters (read-only use)."""
        return self._client

    async def check(self) -> ComponentHealth:
        if self._client is None:
            return ComponentHealth(status="not_configured", message="Redis URL is not configured")
        try:
            if await self._client.ping():
                return ComponentHealth(status="connected", message="Redis is reachable")
        except RedisError as exc:
            logger.warning("Redis health check failed (%s)", type(exc).__name__)
        return ComponentHealth(status="unavailable", message="Redis is not reachable")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
