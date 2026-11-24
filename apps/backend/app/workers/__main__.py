"""Worker process entry point: `python -m app.workers`.

Runs the job engine plus outbox publisher and scheduler in one asyncio
process. Configure via environment:
  UGA_DATABASE_URL, UGA_REDIS_URL, UGA_WORKER_CONCURRENCY,
  UGA_WORKER_JOB_TIMEOUT, UGA_WORKER_POLL_INTERVAL
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from app.core.config import get_settings
from app.database.connection import DatabaseConnection
from app.database.redis_connection import RedisConnection
from app.jobs.queue import RedisJobQueue, UnavailableJobQueue
from app.workers.engine import WorkerEngine
from app.workers.publisher import publish_pending
from app.workers.scheduler import scheduler_tick

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("uga.worker")


async def _amain() -> int:
    settings = get_settings()
    db = DatabaseConnection(
        settings.database_url.get_secret_value() if settings.database_url else None
    )
    if not db.configured:
        logger.error("UGA_DATABASE_URL is not configured; worker cannot start")
        return 2
    session_factory = db._session_factory

    redis = RedisConnection(
        settings.redis_url.get_secret_value() if settings.redis_url else None
    )
    client = redis.client if redis.configured else None
    if client is not None:
        queue = RedisJobQueue(client) if client is not None else UnavailableJobQueue()
    else:
        logger.warning("Redis not configured; queue operations will fail closed")
        queue = UnavailableJobQueue()

    async def publisher() -> int:
        return await publish_pending(session_factory, queue)

    async def scheduler() -> dict:
        return await scheduler_tick(session_factory)

    async def heartbeat() -> None:
        if client is None:
            return
        import json
        from datetime import datetime, timezone
        payload = json.dumps({
            "worker_id": engine.worker_id,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "concurrency": engine.concurrency,
            "jobs_completed": engine.jobs_completed,
            "jobs_failed": engine.jobs_failed,
        })
        await client.hset("uga:workers", engine.worker_id, payload)

    engine = WorkerEngine(
        session_factory=session_factory,
        queue=queue,
        concurrency=int(os.getenv("UGA_WORKER_CONCURRENCY", "2")),
        job_timeout=int(os.getenv("UGA_WORKER_JOB_TIMEOUT", "300")),
        poll_interval=float(os.getenv("UGA_WORKER_POLL_INTERVAL", "2")),
        publisher=publisher,
        scheduler=scheduler,
        heartbeat=heartbeat,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, engine.stop)
        except (NotImplementedError, RuntimeError):
            pass  # Windows: rely on KeyboardInterrupt

    try:
        await engine.run()
    finally:
        await redis.close()
    return 0


def main() -> int:
    try:
        return asyncio.run(_amain())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
