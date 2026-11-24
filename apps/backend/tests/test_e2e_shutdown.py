"""Phase 8 F5: isolated shutdown & resilience tests.

PostgreSQL: universal_growth_test. Redis: compose DB 1.
Never touches production DB/Redis DB 0.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values
from redis.asyncio import Redis
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database.models import Job, JobEvent, JobOutboxEvent, JobSchedule, Project
from app.jobs.queue import RedisJobQueue
from app.schemas.job import JobCreate
from app.schemas.project import ProjectCreate
from app.services.job import JobService
from app.services.project import ProjectService
from app.workers.engine import WorkerEngine
from app.workers.handlers import register_handler
from app.workers.publisher import publish_pending

pytestmark = pytest.mark.skipif(
    not os.environ.get("UGA_TEST_DATABASE_URL"),
    reason="UGA_TEST_DATABASE_URL not set",
)

STATE = {"slow_started": asyncio.Event() if hasattr(asyncio, "Event") else None}
REDIS1 = None


async def _slow_handler(payload, ctx):
    STATE["slow_started"].set()
    await asyncio.sleep(60)
    return {"done": True}


async def _noop(payload, ctx):
    return {"ok": True}


class _NullQueue:
    async def push(self, job_id): pass
    async def pop(self, timeout=None): return None
    async def depth(self): return 0


class _DownQueue:
    async def push(self, job_id):
        from app.jobs.queue import QueueUnavailableError
        raise QueueUnavailableError("down")
    async def pop(self, timeout=None):
        from app.jobs.queue import QueueUnavailableError
        raise QueueUnavailableError("down")
    async def depth(self):
        from app.jobs.queue import QueueUnavailableError
        raise QueueUnavailableError("down")


@pytest.fixture(scope="module")
def env():
    global REDIS1, STATE
    STATE = {"slow_started": None}
    dotenv = dotenv_values(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    engine = create_engine(os.environ["UGA_TEST_DATABASE_URL"])
    with engine.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "universal_growth_test"
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    REDIS1 = re.sub(r"/0(\?.*)?$", "/1", dotenv["UGA_REDIS_URL"])
    yield sf
    engine.dispose()


def _mk(sf, name, job_type="f5.noop", **kw):
    s = sf()
    try:
        p = ProjectService(s).create_project(ProjectCreate(name=name))
        j = JobService(s, _NullQueue()).create_job(
            JobCreate(job_type=job_type, **kw), project_id=p.id, actor="f5"
        )
        return p.id, j.id
    finally:
        s.close()


def _cleanup(sf, pid):
    s = sf()
    try:
        job_ids = [r[0] for r in s.execute(select(Job.id).where(Job.project_id == pid))]
        for model in (JobEvent, JobOutboxEvent):
            for row in s.scalars(select(model).where(model.job_id.in_(job_ids))).all():
                s.delete(row)
            s.flush()
        for model in (Job, JobSchedule):
            for row in s.scalars(select(model).where(model.project_id == pid)).all():
                s.delete(row)
            s.flush()
        proj = s.get(Project, pid)
        if proj:
            s.delete(proj)
        s.commit()
    finally:
        s.close()


def _row(sf, jid):
    s = sf()
    try:
        j = s.get(Job, jid)
        return SimpleNamespace(status=j.status, attempt_count=j.attempt_count,
                               locked_by=j.locked_by, locked_until=j.locked_until,
                               last_error=j.last_error) if j else None
    finally:
        s.close()


# ── F5.2 shutdown while a job is running ───────────────────────────────────

def test_f5_shutdown_during_execution_leaves_recoverable_lease(env):
    asyncio.run(_f5_shutdown(env))


async def _f5_shutdown(sf):
    register_handler("f5.slow", _slow_handler)
    pid, jid = _mk(sf, "F5-SHUT", "f5.slow", max_attempts=3)
    try:
        s = sf()
        await JobService(s, _NullQueue()).enqueue_job(jid, pid, "f5")
        s.close()
        client = Redis.from_url(REDIS1, decode_responses=True)
        queue = RedisJobQueue(client)
        assert await publish_pending(sf, queue) == 1

        started = asyncio.Event()
        orig = _slow_handler

        async def slow2(payload, ctx):
            started.set()
            await asyncio.sleep(60)

        register_handler("f5.slow", slow2)
        eng = WorkerEngine(sf, queue, worker_id="f5-shutdown",
                           concurrency=1, poll_interval=0.1,
                           recovery_interval=60, job_timeout=300)
        task = asyncio.create_task(eng.run())
        await asyncio.wait_for(started.wait(), timeout=10)
        j = _row(sf, jid)
        assert j.status == "running" and j.locked_by == "f5-shutdown"

        # simulate process kill: stop engine WITHOUT waiting for handler
        eng.stop()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
        await client.aclose()

        # job remains running with a lease — NOT falsely completed
        j = _row(sf, jid)
        assert j.status == "running" and j.attempt_count == 1

        # expire the lease and recover — goes back to pending, never completed
        s = sf()
        job = s.get(Job, jid)
        job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit(); s.close()
        rec = WorkerEngine(sf, _NullQueue(), worker_id="f5-rec", recovery_interval=60)
        assert rec.recover_abandoned() == 1
        j = _row(sf, jid)
        assert j.status == "pending" and j.locked_by is None
    finally:
        _cleanup(sf, pid)


# ── F5.3 resilience: queue down / DB down loops keep running ───────────────

def test_f5_worker_survives_queue_outage(env):
    asyncio.run(_f5_queue_down(env))


async def _f5_queue_down(sf):
    """Worker loop must keep polling through QueueUnavailableError."""
    eng = WorkerEngine(sf, _DownQueue(), worker_id="f5-down",
                       concurrency=1, poll_interval=0.1, recovery_interval=0.2)
    task = asyncio.create_task(eng.run())
    await asyncio.sleep(0.6)
    assert not task.done()  # still alive, not crashed
    eng.stop()
    task.cancel()
    try:
        await task
    except BaseException:
        pass


def test_f5_db_outage_does_not_crash_loop(env):
    asyncio.run(_f5_db_down(env))


async def _f5_db_down(sf):
    """A dead DB makes _execute raise inside the loop; loop must survive."""
    dead_engine = create_engine("postgresql+psycopg://uga:bad@127.0.0.1:1/x",
                                connect_args={"connect_timeout": 1})
    dead_sf = sessionmaker(bind=dead_engine, autoflush=False, autocommit=False)
    client = Redis.from_url(REDIS1, decode_responses=True)
    await client.lpush("uga:job-queue", "nonexistent-job-id")
    eng = WorkerEngine(dead_sf, RedisJobQueue(client), worker_id="f5-dbb",
                       concurrency=1, poll_interval=0.1, recovery_interval=60)
    task = asyncio.create_task(eng.run())
    await asyncio.sleep(1.5)
    assert not task.done()  # survived DB connection failure
    eng.stop()
    task.cancel()
    try:
        await task
    except BaseException:
        pass
    # cleanup stray queue entry
    await client.delete("uga:job-queue")
    await client.aclose()
    dead_engine.dispose()


def test_f5_recovery_after_interruption_completes(env):
    """Job recovered after 'crash' then executes exactly once."""
    asyncio.run(_f5_recover(env))


async def _f5_recover(sf):
    register_handler("f5.noop", _noop)
    pid, jid = _mk(sf, "F5-REC", "f5.noop")
    try:
        s = sf()
        await JobService(s, _NullQueue()).enqueue_job(jid, pid, "f5")
        s.close()
        # publish first outbox (job sits queued, never consumed — simulating
        # a queued-but-unclaimed job whose worker then "crashes")
        client = Redis.from_url(REDIS1, decode_responses=True)
        assert await publish_pending(sf, RedisJobQueue(client)) == 1
        await client.delete("uga:job-queue")  # drop the unconsumed delivery
        await client.aclose()
        # crash simulation: running + expired lease, attempt left
        s = sf()
        job = s.get(Job, jid)
        job.status = "running"; job.attempt_count = 1
        job.locked_by = "ghost"; job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit(); s.close()
        rec = WorkerEngine(sf, _NullQueue(), worker_id="f5-rec2", recovery_interval=60)
        rec.recover_abandoned()
        # pending again → promote + publish → real execution
        s = sf()
        JobService(s, _NullQueue()).promote_due_pending()
        s.close()
        client = Redis.from_url(REDIS1, decode_responses=True)
        assert await publish_pending(sf, RedisJobQueue(client)) == 1
        await client.aclose()
        eng = WorkerEngine(sf, RedisJobQueue(Redis.from_url(REDIS1, decode_responses=True)),
                           worker_id="f5-run", concurrency=1, poll_interval=0.1,
                           recovery_interval=60)
        task = asyncio.create_task(eng.run())
        for _ in range(50):
            if _row(sf, jid).status == "completed":
                break
            await asyncio.sleep(0.2)
        eng.stop(); task.cancel()
        try:
            await task
        except BaseException:
            pass
        j = _row(sf, jid)
        assert j.status == "completed" and j.attempt_count == 2
    finally:
        _cleanup(sf, pid)
