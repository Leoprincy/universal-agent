"""Phase 8 F2: isolated end-to-end worker lifecycle test.

Uses the REAL RedisJobQueue against Redis logical DB 1 (isolated from
production DB 0) and the real PostgreSQL test database
(universal_growth_test via UGA_TEST_DATABASE_URL). Skipped unless both
are configured. Registers a deterministic no-op handler in-process only.
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime, timezone

import pytest
from dotenv import dotenv_values
from redis.asyncio import Redis
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Job, JobEvent, Project
from app.jobs.queue import RedisJobQueue
from app.schemas.job import JobCreate
from app.schemas.project import ProjectCreate
from app.services.job import JobService
from app.services.project import ProjectService
from app.workers.engine import WorkerEngine
from app.workers.handlers import get_handler, register_handler
from app.workers.publisher import publish_pending

pytestmark = pytest.mark.skipif(
    not os.environ.get("UGA_TEST_DATABASE_URL"),
    reason="UGA_TEST_DATABASE_URL not set",
)

EXECUTIONS = {"count": 0}


async def _noop_handler(payload, ctx):
    EXECUTIONS["count"] += 1
    return {"ok": True}


def _env_urls():
    env = dotenv_values(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    main_db = env["UGA_DATABASE_URL"]
    test_db = os.environ["UGA_TEST_DATABASE_URL"]
    redis0 = env["UGA_REDIS_URL"]
    # isolate to logical DB 1 — never touch production DB 0
    redis1 = re.sub(r"/0(\?.*)?$", "/1", redis0)
    return main_db, test_db, redis0, redis1


@pytest.fixture(scope="module")
def isolated_env():
    main_db, test_db, redis0, redis1 = _env_urls()
    engine = create_engine(test_db)
    with engine.connect() as c:
        dbname = c.execute(text("select current_database()")).scalar()
        assert dbname == "universal_growth_test", f"wrong DB: {dbname}"
        rev = c.execute(text("select version_num from alembic_version")).scalar()
        assert rev == "b2d4f6a8c1e3", f"test DB not at head: {rev}"
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield sf, redis1
    engine.dispose()


def test_e2e_job_lifecycle_isolated(isolated_env):
    asyncio.run(_e2e(isolated_env))


async def _e2e(isolated_env):
    sf, redis1_url = isolated_env
    # Redis db1 must be empty of our keys
    probe = Redis.from_url(redis1_url, decode_responses=True)
    assert await probe.llen("uga:job-queue") == 0
    assert await probe.hlen("uga:workers") == 0

    register_handler("e2e.noop", _noop_handler)
    assert get_handler("e2e.noop") is not None

    # create project + job in TEST database
    s = sf()
    project = ProjectService(s).create_project(ProjectCreate(name="E2E F2"))
    svc = JobService(s, _NullQueue())
    job = svc.create_job(
        JobCreate(job_type="e2e.noop", payload={"probe": True}),
        project_id=project.id, actor="e2e-test",
    )
    job_id = job.id
    pid = project.id
    s.close()

    # enqueue → outbox row in same txn
    s = sf()
    await JobService(s, _NullQueue()).enqueue_job(job_id, pid, "e2e")
    s.close()

    # publish outbox → real Redis db1
    client = Redis.from_url(redis1_url, decode_responses=True)
    queue = RedisJobQueue(client)
    n = await publish_pending(sf, queue)
    assert n == 1
    assert await client.llen("uga:job-queue") == 1

    # run real worker engine against db1
    engine = WorkerEngine(
        session_factory=sf, queue=queue, worker_id="e2e-worker",
        concurrency=1, poll_interval=0.2, recovery_interval=60,
        job_timeout=10,
    )
    task = asyncio.create_task(engine.run())
    try:
        # wait for completion (max ~15s)
        for _ in range(75):
            s = sf()
            j = s.get(Job, job_id)
            status = j.status if j else None
            s.close()
            if status == "completed":
                break
            await asyncio.sleep(0.2)
        assert status == "completed", f"job stuck at {status}"
        assert EXECUTIONS["count"] == 1
    finally:
        engine.stop()
        task.cancel()
        try:
            await task
        except BaseException:
            pass

    # lifecycle events in order
    s = sf()
    events = s.scalars(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.seq)
    ).all()
    s.close()
    types = [e.event_type for e in events]
    assert types == ["created", "queued", "started", "completed"], types

    # duplicate delivery through the REAL BRPOP consumption path:
    # push the completed job ID again and let a live engine pop it.
    await client.lpush("uga:job-queue", job_id)
    assert await client.llen("uga:job-queue") == 1
    engine2 = WorkerEngine(
        sf, queue, worker_id="e2e-worker-2",
        concurrency=1, poll_interval=0.1, recovery_interval=60,
    )
    task2 = asyncio.create_task(engine2.run())
    try:
        await asyncio.sleep(1.0)  # enough for BRPOP pop + claim attempt
    finally:
        engine2.stop()
        task2.cancel()
        try:
            await task2
        except BaseException:
            pass
    assert EXECUTIONS["count"] == 1
    assert await client.llen("uga:job-queue") == 0  # duplicate was consumed
    s = sf()
    j = s.get(Job, job_id)
    assert j.status == "completed" and j.attempt_count == 1
    ev_count = len(s.scalars(select(JobEvent).where(JobEvent.job_id == job_id)).all())
    s.close()
    assert ev_count == 4  # no extra lifecycle events from duplicate delivery
    # remove the duplicate we pushed so db1 is clean
    await client.lrem("uga:job-queue", 0, job_id)

    # cleanup test records (RESTRICT order: events, outbox, jobs, project)
    s = sf()
    from app.database.models import JobOutboxEvent
    for model in (JobEvent, JobOutboxEvent, Job):
        for row in s.scalars(select(model).where(model.project_id == pid)).all():
            s.delete(row)
        s.flush()
    proj = s.get(Project, pid)
    s.delete(proj)
    s.commit()
    s.close()

    # worker heartbeat key in db1 may exist — clean it too
    await client.delete("uga:workers")
    await client.aclose()
    await probe.aclose()


class _NullQueue:
    async def push(self, job_id): pass
    async def pop(self, timeout=None): return None
    async def depth(self): return 0
