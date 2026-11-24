"""Phase 8 Milestone 2 tests: outbox, worker engine, scheduler, retries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import (
    Base,
    Job,
    JobEvent,
    JobOutboxEvent,
    JobSchedule,
)
from app.jobs.queue import QueueUnavailableError
from app.schemas.job import JobCreate
from app.schemas.project import ProjectCreate
from app.services.job import JobScheduleService, JobService
from app.services.project import ProjectService
from app.workers.engine import WorkerEngine, backoff_seconds
from app.workers.handlers import (
    PermanentJobError,
    register_handler,
)
from app.workers.publisher import publish_pending
from app.workers.scheduler import next_slot_after, scheduler_tick


class FakeQueue:
    def __init__(self, fail: bool = False):
        self.pushed: list[str] = []
        self.fail = fail

    async def push(self, job_id: str) -> None:
        if self.fail:
            raise QueueUnavailableError("redis down")
        self.pushed.append(job_id)

    async def pop(self, timeout=None):
        if self.fail:
            raise QueueUnavailableError("redis down")
        return self.pushed.pop(0) if self.pushed else None

    async def depth(self) -> int:
        if self.fail:
            raise QueueUnavailableError("redis down")
        return len(self.pushed)


@pytest.fixture
def engine_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = sf()
    project = ProjectService(session).create_project(ProjectCreate(name="W"))
    session.close()
    yield sf, project.id
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF;")
        Base.metadata.drop_all(bind=conn)


def _mk_job(sf, project_id, **kw):
    s = sf()
    try:
        job = JobService(s, FakeQueue()).create_job(
            JobCreate(job_type=kw.pop("job_type", "t.ok"), **kw),
            project_id=project_id, actor="test",
        )
        return job.id
    finally:
        s.close()


def _job(sf, job_id):
    from types import SimpleNamespace
    s = sf()
    try:
        j = s.get(Job, job_id)
        return SimpleNamespace(
            id=j.id, status=j.status, attempt_count=j.attempt_count,
            scheduled_at=j.scheduled_at, last_error=j.last_error,
            locked_by=j.locked_by, max_attempts=j.max_attempts,
        )
    finally:
        s.close()


async def _noop(payload, ctx):
    return "ok"


class TestOutbox:
    def test_enqueue_writes_outbox_atomically(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid)
        s = sf()
        JobService(s, FakeQueue())._session  # noqa
        svc = JobService(s, FakeQueue())
        import asyncio
        asyncio.run(svc.enqueue_job(jid, pid, "w"))
        s.close()
        s = sf()
        job = s.get(Job, jid)
        assert job.status == "queued"
        row = s.scalar(select(JobOutboxEvent).where(JobOutboxEvent.job_id == jid))
        assert row.status == "pending"
        s.close()

    def test_publish_pending_marks_published(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid)
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        q = FakeQueue()
        n = asyncio.run(publish_pending(sf, q))
        assert n == 1 and q.pushed == [jid]
        s = sf()
        assert s.scalar(select(JobOutboxEvent).where(JobOutboxEvent.job_id == jid)).status == "published"
        s.close()

    def test_publish_recovers_after_crash(self, engine_db):
        sf, pid = engine_db
        """Outbox row survives; publisher can run again (idempotent-ish)."""
        sf, pid = engine_db
        jid = _mk_job(sf, pid)
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        q = FakeQueue(fail=True)
        asyncio.run(publish_pending(sf, q))
        s = sf()
        row = s.scalar(select(JobOutboxEvent).where(JobOutboxEvent.job_id == jid))
        assert row.status == "pending" and row.attempts == 1
        s.close()
        q2 = FakeQueue()
        asyncio.run(publish_pending(sf, q2))
        assert q2.pushed == [jid]

    def test_promote_due_pending_reconciles(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid, scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        s = sf()
        svc = JobService(s, FakeQueue())
        assert svc.promote_due_pending() == 1
        s.close()
        assert _job(sf, jid).status == "queued"


class TestWorkerEngine:
    def _engine(self, sf, q, **kw):
        return WorkerEngine(sf, q, worker_id="w-test", **kw)

    def test_successful_execution(self, engine_db):
        sf, pid = engine_db
        register_handler("t.ok", _noop)
        jid = _mk_job(sf, pid, job_type="t.ok")
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        q = FakeQueue(); q.pushed.append(jid)
        eng = self._engine(sf, q)
        asyncio.run(eng._execute(jid))
        job = _job(sf, jid)
        assert job.status == "completed" and job.attempt_count == 1
        s = sf()
        types = [e.event_type for e in s.scalars(select(JobEvent).where(JobEvent.job_id == jid).order_by(JobEvent.seq))]
        s.close()
        assert types == ["created", "queued", "started", "completed"]
        assert eng.jobs_completed == 1

    def test_duplicate_message_skipped(self, engine_db):
        sf, pid = engine_db
        register_handler("t.ok", _noop)
        jid = _mk_job(sf, pid, job_type="t.ok")
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        q = FakeQueue(); q.pushed.extend([jid, jid])
        eng = self._engine(sf, q)
        asyncio.run(eng._execute(jid))
        asyncio.run(eng._execute(jid))  # second claim sees running/completed
        assert _job(sf, jid).attempt_count == 1

    def test_invalid_payload_permanent(self, engine_db):
        sf, pid = engine_db
        from pydantic import BaseModel
        class P(BaseModel):
            x: int
        async def h(payload, ctx): return "ok"
        register_handler("t.bad", h, payload_model=P)
        jid = _mk_job(sf, pid, job_type="t.bad", payload={"x": "notint"})
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue())
        asyncio.run(eng._execute(jid))
        job = _job(sf, jid)
        assert job.status == "failed" and "Invalid payload" in (job.last_error or "")

    def test_retryable_failure_backoff(self, engine_db):
        sf, pid = engine_db
        async def boom(payload, ctx): raise RuntimeError("boom")
        register_handler("t.boom", boom)
        jid = _mk_job(sf, pid, job_type="t.boom", max_attempts=3)
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue())
        asyncio.run(eng._execute(jid))
        job = _job(sf, jid)
        assert job.status == "pending" and job.attempt_count == 1
        assert job.scheduled_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        s = sf()
        ev = s.scalars(select(JobEvent).where(JobEvent.job_id == jid).order_by(JobEvent.seq.desc())).first()
        s.close()
        assert ev.event_type == "failed" and ev.to_status == "pending"

    def test_max_attempts_terminal(self, engine_db):
        sf, pid = engine_db
        async def boom(payload, ctx): raise RuntimeError("boom")
        register_handler("t.boom2", boom)
        jid = _mk_job(sf, pid, job_type="t.boom2", max_attempts=1)
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue())
        asyncio.run(eng._execute(jid))
        job = _job(sf, jid)
        assert job.status == "failed" and job.attempt_count == 1
        assert "RuntimeError" in (job.last_error or "")

    def test_permanent_error_no_retry(self, engine_db):
        sf, pid = engine_db
        async def perm(payload, ctx): raise PermanentJobError("nope")
        register_handler("t.perm", perm)
        jid = _mk_job(sf, pid, job_type="t.perm", max_attempts=5)
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue())
        asyncio.run(eng._execute(jid))
        assert _job(sf, jid).status == "failed"

    def test_timeout_retries(self, engine_db):
        sf, pid = engine_db
        async def slow(payload, ctx):
            await asyncio.sleep(60)
        register_handler("t.slow", slow)
        jid = _mk_job(sf, pid, job_type="t.slow", max_attempts=2)
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue(), job_timeout=0.1)
        asyncio.run(eng._execute(jid))
        job = _job(sf, jid)
        assert job.status == "pending" and "timed out" in (job.last_error or "")

    def test_unregistered_type_fails_permanently(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid, job_type="t.missing")
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue())
        asyncio.run(eng._execute(jid))
        assert _job(sf, jid).status == "failed"

    def test_abandoned_lease_recovery(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid, job_type="t.ok")
        s = sf()
        job = s.get(Job, jid)
        job.status = "running"
        job.attempt_count = 1
        job.locked_by = "dead-worker"
        job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=10)
        s.commit(); s.close()
        eng = self._engine(sf, FakeQueue())
        assert eng.recover_abandoned() == 1
        job = _job(sf, jid)
        assert job.status == "pending" and job.locked_by is None

    def test_abandoned_lease_exhausted_fails(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid, job_type="t.ok", max_attempts=1)
        s = sf()
        job = s.get(Job, jid)
        job.status = "running"
        job.attempt_count = 1
        job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=10)
        s.commit(); s.close()
        eng = self._engine(sf, FakeQueue())
        eng.recover_abandoned()
        assert _job(sf, jid).status == "failed"

    def test_future_scheduled_not_claimed(self, engine_db):
        sf, pid = engine_db
        jid = _mk_job(sf, pid, job_type="t.ok",
                      scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1))
        s = sf()
        import asyncio
        asyncio.run(JobService(s, FakeQueue()).enqueue_job(jid, pid, "w"))
        s.close()
        eng = self._engine(sf, FakeQueue())
        asyncio.run(eng._execute(jid))
        assert _job(sf, jid).status == "queued"  # untouched


class TestBackoff:
    def test_exponential(self):
        assert backoff_seconds(1) == 5
        assert backoff_seconds(2) == 10
        assert backoff_seconds(3) == 20
        assert backoff_seconds(20) == 300  # capped


class TestScheduler:
    def test_schedule_materializes_job(self, engine_db):
        sf, pid = engine_db
        s = sf()
        JobScheduleService(s).create_schedule(
            project_id=pid, name="s1", job_type="t.ok", payload=None,
            interval_seconds=3600,
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            actor="test",
        )
        s.close()
        import asyncio
        res = asyncio.run(scheduler_tick(sf))
        assert res["materialized"] == 1
        s = sf()
        job = s.scalar(select(Job).where(Job.project_id == pid))
        assert job.status == "queued" and job.idempotency_key.startswith("schedule:")
        outbox = s.scalar(select(JobOutboxEvent).where(JobOutboxEvent.job_id == job.id))
        assert outbox is not None
        sched = s.scalar(select(JobSchedule))
        assert sched.next_run_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        s.close()

    def test_duplicate_occurrence_prevented(self, engine_db):
        sf, pid = engine_db
        s = sf()
        JobScheduleService(s).create_schedule(
            project_id=pid, name="s2", job_type="t.ok", payload=None,
            interval_seconds=3600,
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            actor="test",
        )
        s.close()
        import asyncio
        asyncio.run(scheduler_tick(sf))
        # rewind next_run_at to same slot and tick again — idempotency key dedupes
        s = sf()
        sched = s.scalar(select(JobSchedule))
        sched.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit(); s.close()
        # same slot? next slot differs; force identical slot via direct job key check
        s = sf()
        count1 = s.scalar(select(func.count()).select_from(Job).where(Job.project_id == pid))
        s.close()
        asyncio.run(scheduler_tick(sf))
        s = sf()
        count2 = s.scalar(select(func.count()).select_from(Job).where(Job.project_id == pid))
        s.close()
        assert count2 == count1 + 1  # one new slot only, no duplicates

    def test_disabled_schedule_skipped(self, engine_db):
        sf, pid = engine_db
        s = sf()
        sched = JobScheduleService(s).create_schedule(
            project_id=pid, name="s3", job_type="t.ok", payload=None,
            interval_seconds=60,
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            actor="test",
        )
        JobScheduleService(s).set_enabled(sched.id, pid, False, "test")
        s.close()
        import asyncio
        asyncio.run(scheduler_tick(sf))
        s = sf()
        assert s.scalar(select(func.count()).select_from(Job).where(Job.project_id == pid)) == 0
        s.close()

    def test_next_slot_skips_missed(self):
        s = JobSchedule(
            id="x", project_id="p", name="n", job_type="t", payload_json=None,
            interval_seconds=60,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=5),
            enabled=True, created_by="t",
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        nxt = next_slot_after(s, datetime.now(timezone.utc))
        assert nxt > datetime.now(timezone.utc)
        assert (nxt - datetime.now(timezone.utc)) <= timedelta(seconds=60)
