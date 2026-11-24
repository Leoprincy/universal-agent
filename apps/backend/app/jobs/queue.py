"""Queue abstraction for Phase 8.

The queue carries only job ID references — PostgreSQL `jobs` rows are the
durable source of truth. Adapters are async to match the Redis client; job
services stay synchronous and are invoked from async routes.
"""

from __future__ import annotations

from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

QUEUE_KEY = "uga:job-queue"


class QueueUnavailableError(Exception):
    """Raised when the queue backend cannot accept or report jobs."""


class JobQueue(Protocol):
    async def push(self, job_id: str) -> None: ...
    async def pop(self, timeout: float | None = None) -> str | None: ...
    async def depth(self) -> int: ...


class RedisJobQueue:
    """Redis list-backed queue. LPUSH + future BRPOP gives FIFO order."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def push(self, job_id: str) -> None:
        try:
            await self._client.lpush(QUEUE_KEY, job_id)
        except RedisError as exc:
            raise QueueUnavailableError(f"Redis queue push failed: {type(exc).__name__}") from exc

    async def depth(self) -> int:
        try:
            return int(await self._client.llen(QUEUE_KEY))
        except RedisError as exc:
            raise QueueUnavailableError(f"Redis queue depth failed: {type(exc).__name__}") from exc

    async def pop(self, timeout: float | None = None) -> str | None:
        try:
            if timeout is None:
                item = await self._client.brpop(QUEUE_KEY, timeout=0)
            else:
                item = await self._client.brpop(QUEUE_KEY, timeout=max(1, int(timeout)))
        except RedisError as exc:
            raise QueueUnavailableError(f"Redis queue pop failed: {type(exc).__name__}") from exc
        if item is None:
            return None
        return item[1].decode() if isinstance(item[1], bytes) else str(item[1])


class UnavailableJobQueue:
    """Used when Redis is not configured — every operation fails closed."""

    async def push(self, job_id: str) -> None:
        raise QueueUnavailableError("Job queue is not configured")

    async def pop(self, timeout: float | None = None) -> str | None:
        raise QueueUnavailableError("Job queue is not configured")

    async def depth(self) -> int:
        raise QueueUnavailableError("Job queue is not configured")


class QueueHealthCheck:
    """AsyncConnectivityCheck adapter reporting queue depth, not workers."""

    def __init__(self, queue: JobQueue) -> None:
        self._queue = queue

    async def check(self):
        from app.schemas.health import ComponentHealth

        try:
            depth = await self._queue.depth()
            return ComponentHealth(
                status="connected",
                message=f"Queue reachable (depth={depth}); worker status: see /api/v1/ops/overview",
            )
        except QueueUnavailableError:
            return ComponentHealth(
                status="unavailable", message="Job queue is not reachable"
            )
