"""Phase 8 F3: failure & recovery scenarios in the isolated environment.

PostgreSQL: universal_growth_test (UGA_TEST_DATABASE_URL).
Redis: compose instance logical DB 1 (isolated from production DB 0).
Skips cleanly when UGA_TEST_DATABASE_URL is not set.
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

from app.database.models import (
    Base, Job, JobEvent, JobOutboxEvent, JobSchedule, Project,
)
from app.jobs.queue import RedisJobQueue
from app.schemas.job import JobCreate
from app.schemas.project import ProjectCreate
from app.services.job import JobScheduleService, JobService
from app.services.project import ProjectService
from app.workers.engine import WorkerEngine
from app.workers.handlers import PermanentJobError, register_handler
from app.workers.publisher import publish_pending
from app.workers.scheduler import scheduler_tick

pytestmark = pytest.mark.skipif(
    not os.environ.get("UGA_TEST_DATABASE_URL"),
    reason="UGA_TEST_DATABASE_URL not set",
)

STATE = {"flaky": 0, "always": 0, "noop": 0}
REDIS1 = None


async def _noop(payload, ctx):
    STATE["noop"] += 1
    return {"ok": True}


async def _flaky(payload, ctx):
    STATE["flaky"] += 1
    if STATE["flaky"] == 1:
        raise RuntimeError("transient-e2e-failure")
    return {"ok": True}


async def _perm(payload, ctx):
    raise PermanentJobError("e2e-permanent")


async def _always_fail(payload, ctx):
    STATE["always"] += 1
    raise RuntimeError("always-fails")


async def _sched(payload, ctx):
    return {"scheduled": True}


class _NullQueue:
    async def push(self, job_id): pass
    async def pop(self, timeout=None): return None
    async def depth(self): return 0


@pytest.fixture(scope="module")
def env():
    global REDIS1
    dotenv = dotenv_values(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    test_db = os.environ["UGA_TEST_DATABASE_URL"]
    redis1 = re.sub(r"/0(\?.*)?$", "/1", dotenv["UGA_REDIS_URL"])
    engine = create_engine(test_db)
    with engine.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "universal_growth_test"
        assert c.execute(text("select version_num from alembic_version")).scalar() == "b2d4f6a8c1e3"
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    REDIS1 = redis1
    yield sf
    engine.dispose()


def _mk(sf, name, job_type, **kw):
    s = sf()
    try:
        p = ProjectService(s).create_project(ProjectCreate(name=name))
        j = JobService(s, _NullQueue()).create_job(
            JobCreate(job_type=job_type, **kw), project_id=p.id, actor="f3"
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
        return SimpleNamespace(
            status=j.status, attempt_count=j.attempt_count,
            scheduled_at=j.scheduled_at, last_error=j.last_error,
            locked_by=j.locked_by,
        ) if j else None
    finally:
        s.close()


def _events(sf, jid):
    s = sf()
    try:
        return [e.event_type for e in s.scalars(
            select(JobEvent).where(JobEvent.job_id == jid).order_by(JobEvent.seq)
        ).all()]
    finally:
        s.close()


async def _enqueue_publish(sf, pid, jid):
    s = sf()
    await JobService(s, _NullQueue()).enqueue_job(jid, pid, "f3")
    s.close()
    client = Redis.from_url(REDIS1, decode_responses=True)
    n = await publish_pending(sf, RedisJobQueue(client))
    await client.aclose()
    return n


async def _force_due_and_republish(sf, jid):
    s = sf()
    job = s.get(Job, jid)
    job.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    s.commit()
    JobService(s, _NullQueue()).promote_due_pending()
    s.close()
    client = Redis.from_url(REDIS1, decode_responses=True)
    await publish_pending(sf, RedisJobQueue(client))
    await client.aclose()


async def _run_until(sf, jid, want, timeout=12.0):
    client = Redis.from_url(REDIS1, decode_responses=True)
    eng = WorkerEngine(sf, RedisJobQueue(client), worker_id="f3-worker",
                       concurrency=1, poll_interval=0.1,
                       recovery_interval=60, job_timeout=10)
    task = asyncio.create_task(eng.run())
    status = None
    try:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            status = _row(sf, jid).status
            if status == want:
                return eng, status
            await asyncio.sleep(0.2)
        return eng, status
    finally:
        eng.stop()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
        await client.aclose()


async def _brpop_noise_then_stop(sf, jid, seconds=0.8):
    """Push jid to db1 queue and let a real engine consume it, then stop."""
    client = Redis.from_url(REDIS1, decode_responses=True)
    await client.lpush("uga:job-queue", jid)
    eng = WorkerEngine(sf, RedisJobQueue(client), worker_id="f3-noise",
                       concurrency=1, poll_interval=0.1, recovery_interval=60)
    task = asyncio.create_task(eng.run())
    await asyncio.sleep(seconds)
    eng.stop()
    task.cancel()
    try:
        await task
    except BaseException:
        pass
    await client.aclose()


# ── F3.1 retryable failure → backoff → success ─────────────────────────────

def test_f3_1_retryable_failure_then_success(env):
    asyncio.run(_f3_1(env))


async def _f3_1(sf):
    register_handler("f3.flaky", _flaky)
    STATE["flaky"] = 0
    pid, jid = _mk(sf, "F3-1", "f3.flaky", max_attempts=3)
    try:
        assert await _enqueue_publish(sf, pid, jid) == 1
        eng, status = await _run_until(sf, jid, "pending")
        j = _row(sf, jid)
        assert j.status == "pending" and j.attempt_count == 1
        sa = j.scheduled_at
        sa = sa.replace(tzinfo=timezone.utc) if sa.tzinfo is None else sa
        assert sa > datetime.now(timezone.utc)  # backed off
        assert "transient-e2e-failure" in (j.last_error or "")
        await _force_due_and_republish(sf, jid)
        eng, status = await _run_until(sf, jid, "completed")
        assert status == "completed"
        j = _row(sf, jid)
        assert j.attempt_count == 2 and STATE["flaky"] == 2
        assert _events(sf, jid) == [
            "created", "queued", "started", "failed",
            "queued", "started", "completed",
        ]
    finally:
        _cleanup(sf, pid)


# ── F3.2 permanent failure ─────────────────────────────────────────────────

def test_f3_2_permanent_failure(env):
    asyncio.run(_f3_2(env))


async def _f3_2(sf):
    register_handler("f3.perm", _perm)
    pid, jid = _mk(sf, "F3-2", "f3.perm", max_attempts=5)
    try:
        await _enqueue_publish(sf, pid, jid)
        eng, status = await _run_until(sf, jid, "failed")
        j = _row(sf, jid)
        assert j.status == "failed" and j.attempt_count == 1  # no retry at max=5
        assert "e2e-permanent" in (j.last_error or "")
        assert _events(sf, jid) == ["created", "queued", "started", "failed"]
    finally:
        _cleanup(sf, pid)


# ── F3.3 max-attempt exhaustion ────────────────────────────────────────────

def test_f3_3_max_attempts_exhaustion(env):
    asyncio.run(_f3_3(env))


async def _f3_3(sf):
    register_handler("f3.always", _always_fail)
    STATE["always"] = 0
    pid, jid = _mk(sf, "F3-3", "f3.always", max_attempts=2)
    try:
        await _enqueue_publish(sf, pid, jid)
        # attempt 1 → pending; force due → attempt 2 → failed (max)
        eng, status = await _run_until(sf, jid, "pending")
        await _force_due_and_republish(sf, jid)
        eng, status = await _run_until(sf, jid, "failed")
        j = _row(sf, jid)
        assert j.status == "failed" and j.attempt_count == 2
        assert STATE["always"] == 2
        # extra queue noise must not execute a 3rd attempt
        await _brpop_noise_then_stop(sf, jid)
        assert STATE["always"] == 2
        assert _row(sf, jid).status == "failed"
    finally:
        _cleanup(sf, pid)


# ── F3.4 abandoned lease recovery ──────────────────────────────────────────

def test_f3_4_abandoned_lease_recovery(env):
    asyncio.run(_f3_4(env))


async def _f3_4(sf):
    register_handler("f3.noop", _noop)
    STATE["noop"] = 0
    pid, jid = _mk(sf, "F3-4", "f3.noop", max_attempts=3)
    pid2, jid2 = _mk(sf, "F3-4b", "f3.noop", max_attempts=1)
    try:
        # crashed-worker simulation: running + expired lease
        s = sf()
        job = s.get(Job, jid)
        job.status = "running"; job.attempt_count = 1
        job.locked_by = "dead-worker"
        job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=5)
        job.started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        job2 = s.get(Job, jid2)
        job2.status = "running"; job2.attempt_count = 1
        job2.locked_until = datetime.now(timezone.utc) - timedelta(seconds=5)
        s.commit(); s.close()
        eng = WorkerEngine(sf, _NullQueue(), worker_id="f3-rec", recovery_interval=60)
        assert eng.recover_abandoned() == 2
        j = _row(sf, jid)
        assert j.status == "pending" and j.locked_by is None  # never completed
        assert _row(sf, jid2).status == "failed"  # attempts exhausted
        # recovered job runs to completion via real path
        await _enqueue_publish(sf, pid, jid)
        eng, status = await _run_until(sf, jid, "completed")
        assert status == "completed" and STATE["noop"] == 1
    finally:
        _cleanup(sf, pid)
        _cleanup(sf, pid2)


# ── F3.5 outbox recovery ───────────────────────────────────────────────────

def test_f3_5_outbox_recovery(env):
    asyncio.run(_f3_5(env))


async def _f3_5(sf):
    register_handler("f3.noop", _noop)
    STATE["noop"] = 0
    pid, jid = _mk(sf, "F3-5", "f3.noop")
    try:
        s = sf()
        await JobService(s, _NullQueue()).enqueue_job(jid, pid, "f3")
        s.close()

        class DownQueue:
            async def push(self, job_id):
                from app.jobs.queue import QueueUnavailableError
                raise QueueUnavailableError("simulated outage")

        assert await publish_pending(sf, DownQueue()) == 0
        s = sf()
        row = s.scalar(select(JobOutboxEvent).where(JobOutboxEvent.job_id == jid))
        assert row.status == "pending" and row.attempts == 1  # recoverable
        s.close()
        # restore → republish
        client = Redis.from_url(REDIS1, decode_responses=True)
        assert await publish_pending(sf, RedisJobQueue(client)) == 1
        assert await client.llen("uga:job-queue") == 1
        await client.aclose()
        eng, status = await _run_until(sf, jid, "completed")
        assert status == "completed" and STATE["noop"] == 1
        # duplicate outbox publication is a no-op; redelivery doesn't re-execute
        client = Redis.from_url(REDIS1, decode_responses=True)
        assert await publish_pending(sf, RedisJobQueue(client)) == 0
        await _brpop_noise_then_stop(sf, jid)
        assert STATE["noop"] == 1
        await client.aclose()
    finally:
        _cleanup(sf, pid)


# ── F3.6 scheduler recovery & dedup ────────────────────────────────────────

def test_f3_6_scheduler_recovery_and_dedup(env):
    asyncio.run(_f3_6(env))


async def _f3_6(sf):
    register_handler("f3.sched", _sched)
    s = sf()
    proj = ProjectService(s).create_project(ProjectCreate(name="F3-6"))
    pid = proj.id
    s.close()
    try:
        s = sf()
        JobScheduleService(s).create_schedule(
            project_id=pid, name="f3-sched", job_type="f3.sched", payload=None,
            interval_seconds=3600,
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            actor="f3")
        s.close()
        res = await scheduler_tick(sf)
        assert res["materialized"] == 1
        s = sf()
        job = s.scalar(select(Job).where(Job.project_id == pid))
        jid = job.id
        slot = job.scheduled_at
        assert job.status == "queued"
        s.close()
        # simulate restart + same-slot re-tick → idempotency dedupes
        s = sf()
        sched = s.scalar(select(JobSchedule).where(JobSchedule.project_id == pid))
        sched.next_run_at = slot  # rewind to the same occurrence slot
        s.commit(); s.close()
        await scheduler_tick(sf)
        s = sf()
        jobs = s.scalars(select(Job).where(Job.project_id == pid)).all()
        assert len(jobs) == 1  # no duplicate occurrence
        s.close()
        # execute via real path
        client = Redis.from_url(REDIS1, decode_responses=True)
        assert await publish_pending(sf, RedisJobQueue(client)) == 1
        await client.aclose()
        eng, status = await _run_until(sf, jid, "completed")
        assert status == "completed"
        # schedule survives restart semantics: still enabled, next slot future
        s = sf()
        sched = s.scalar(select(JobSchedule))
        nxt = sched.next_run_at
        nxt = nxt.replace(tzinfo=timezone.utc) if nxt.tzinfo is None else nxt
        assert sched.enabled and nxt > datetime.now(timezone.utc)
        s.close()
    finally:
        _cleanup(sf, pid)
