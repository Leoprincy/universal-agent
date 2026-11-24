"""Phase 8 Milestone 3: operational monitoring tests."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base, Job, JobOutboxEvent, JobSchedule
from app.jobs.queue import QueueUnavailableError
from app.schemas.project import ProjectCreate
from app.services.job import JobService
from app.services.ops import OpsService
from app.services.project import ProjectService
from app.schemas.job import JobCreate


class FakeQueue:
    def __init__(self, depth_val=0, fail=False):
        self._depth = depth_val
        self.fail = fail
    async def push(self, job_id): pass
    async def pop(self, timeout=None): return None
    async def depth(self):
        if self.fail: raise QueueUnavailableError("down")
        return self._depth


class FakeRedis:
    def __init__(self, data=None):
        self.data = data or {}
    async def hgetall(self, key):
        return self.data.get(key, {})


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = sf()
    p = ProjectService(s).create_project(ProjectCreate(name="Ops"))
    s.close()
    yield sf, p.id
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF;")
        Base.metadata.drop_all(bind=conn)


def _mk(sf, pid, **kw):
    s = sf()
    try:
        return JobService(s, FakeQueue()).create_job(
            JobCreate(job_type=kw.pop("job_type", "t.x"), **kw),
            project_id=pid, actor="t")
    finally:
        s.close()


def test_overview_empty(db):
    sf, pid = db
    s = sf()
    ops = OpsService(s, FakeQueue(), FakeRedis())
    ov = asyncio.run(ops.overview())
    s.close()
    assert ov["active_workers"] == 0
    assert ov["worker_heartbeat_store"] == "available"
    assert ov["queue_depth"] == 0
    assert ov["jobs"]["pending"] == 0
    assert ov["outbox"]["pending"] == 0
    assert ov["expired_leases"] == 0


def test_worker_liveness(db):
    sf, pid = db
    fresh = {"worker_id": "w1", "last_seen": datetime.now(timezone.utc).isoformat(),
             "concurrency": 2, "jobs_completed": 3, "jobs_failed": 0}
    stale = {"worker_id": "w2", "last_seen": (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()}
    redis = FakeRedis({"uga:workers": {"w1": json.dumps(fresh), "w2": json.dumps(stale)}})
    s = sf()
    ops = OpsService(s, FakeQueue(), redis)
    workers, ok = asyncio.run(ops.list_workers())
    s.close()
    assert ok and len(workers) == 2
    assert workers[0]["alive"] is True and workers[1]["alive"] is False
    assert workers[0]["jobs_completed"] == 3


def test_no_redis_means_no_workers(db):
    sf, pid = db
    s = sf()
    ops = OpsService(s, FakeQueue(), None)
    workers, ok = asyncio.run(ops.list_workers())
    ov = asyncio.run(ops.overview())
    s.close()
    assert workers == [] and ok is False
    assert ov["worker_heartbeat_store"] == "unavailable"


def test_job_counts_and_outbox(db):
    sf, pid = db
    j1 = _mk(sf, pid)
    j2 = _mk(sf, pid)
    s = sf()
    svc = JobService(s, FakeQueue())
    asyncio.run(svc.enqueue_job(j1.id, pid, "w"))
    svc.transition_job(j1.id, pid, "running", "w")
    svc.transition_job(j1.id, pid, "completed", "w")
    svc.transition_job(j2.id, pid, "cancelled", "w")
    s.close()
    s = sf()
    ops = OpsService(s, FakeQueue(), FakeRedis())
    counts = ops.job_counts()
    outbox = ops.outbox_counts()
    s.close()
    assert counts["completed"] == 1 and counts["cancelled"] == 1
    assert outbox["pending"] == 1


def test_expired_leases_and_retries(db):
    sf, pid = db
    j = _mk(sf, pid, max_attempts=3)
    s = sf()
    job = s.get(Job, j.id)
    job.status = "running"
    job.attempt_count = 2
    job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    s.commit(); s.close()
    s = sf()
    ops = OpsService(s, FakeQueue(), FakeRedis())
    assert ops.expired_leases() == 1
    assert ops.retry_activity()["jobs_with_retries"] == 1
    s.close()


def test_queue_depth_unavailable(db):
    sf, pid = db
    s = sf()
    ops = OpsService(s, FakeQueue(fail=True), FakeRedis())
    assert asyncio.run(ops.queue_depth()) is None
    ov = asyncio.run(ops.overview())
    s.close()
    assert ov["queue_depth"] is None


def test_schedule_summary(db):
    sf, pid = db
    from app.services.job import JobScheduleService
    s = sf()
    JobScheduleService(s).create_schedule(
        project_id=pid, name="nightly", job_type="t.x", payload=None,
        interval_seconds=3600,
        next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
        actor="t")
    s.close()
    s = sf()
    ops = OpsService(s, FakeQueue(), FakeRedis())
    summ = ops.schedule_summary()
    s.close()
    assert len(summ) == 1 and summ[0]["name"] == "nightly" and summ[0]["enabled"] is True


def test_project_job_stats(db):
    sf, pid = db
    _mk(sf, pid)
    _mk(sf, pid)
    s = sf()
    stats = JobService(s, FakeQueue()).job_stats(pid)
    s.close()
    assert stats["pending"] == 2 and stats["with_retries"] == 0
