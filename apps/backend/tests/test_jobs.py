"""Phase 8 Milestone 1: persistent job infrastructure tests."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ApplicationError, ConflictError, NotFoundError
from app.database.models import Base, Job, JobEvent, Project
from app.jobs.queue import QueueUnavailableError
from app.schemas.job import JobCreate
from app.schemas.project import ProjectCreate
from app.services.job import JobService
from app.services.project import ProjectService


class FakeQueue:
    def __init__(self, fail: bool = False):
        self.pushed: list[str] = []
        self.fail = fail

    async def push(self, job_id: str) -> None:
        if self.fail:
            raise QueueUnavailableError("redis down")
        self.pushed.append(job_id)

    async def depth(self) -> int:
        if self.fail:
            raise QueueUnavailableError("redis down")
        return len(self.pushed)

    async def pop(self, timeout: float | None = None) -> str | None:
        if self.fail:
            raise QueueUnavailableError("redis down")
        return self.pushed.pop(0) if self.pushed else None


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys = OFF;")
            Base.metadata.drop_all(bind=conn)


@pytest.fixture
def project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Jobs Project"))


@pytest.fixture
def other_project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Other"))


@pytest.fixture
def queue():
    return FakeQueue()


@pytest.fixture
def service(db_session, queue):
    return JobService(db_session, queue=queue)


def _mk(svc, project, **kw):
    return svc.create_job(
        JobCreate(job_type=kw.pop("job_type", "test.job"), **kw),
        project_id=project.id,
        actor="tester",
    )


def _run(coro):
    return asyncio.run(coro)


class TestJobCreation:
    def test_create_pending(self, service, project):
        job = _mk(service, project, payload={"a": 1}, priority=5)
        assert job.status == "pending"
        assert job.payload_json == {"a": 1}
        assert job.created_by == "tester"
        assert job.max_attempts == 3

    def test_idempotent_create_returns_existing(self, service, project):
        j1 = _mk(service, project, idempotency_key="k1")
        j2 = _mk(service, project, idempotency_key="k1")
        assert j1.id == j2.id

    def test_idempotency_scoped_per_project(self, service, project, other_project):
        j1 = _mk(service, project, idempotency_key="k1")
        j2 = _mk(service, other_project, idempotency_key="k1")
        assert j1.id != j2.id

    def test_scheduled_at_future(self, service, project):
        job = _mk(
            service, project,
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert job.scheduled_at is not None


class TestJobRetrievalAndListing:
    def test_get(self, service, project):
        job = _mk(service, project)
        assert service.get_job(job.id, project.id).id == job.id

    def test_cross_project_404(self, service, project, other_project):
        job = _mk(service, project)
        with pytest.raises(NotFoundError):
            service.get_job(job.id, other_project.id)
        with pytest.raises(NotFoundError):
            service.cancel_job(job.id, other_project.id, "x")

    def test_list_filters_and_pagination(self, service, project):
        _mk(service, project, job_type="a.b")
        _mk(service, project, job_type="c.d")
        _mk(service, project, job_type="a.b")
        items, total = service.list_jobs(project.id, job_type="a.b")
        assert total == 2 and len(items) == 2
        items2, total2 = service.list_jobs(project.id, limit=2, offset=0)
        assert total2 == 3 and len(items2) == 2
        with pytest.raises(ApplicationError):
            service.list_jobs(project.id, status="bogus")


class TestLifecycle:
    def test_enqueue_pending(self, service, project, queue, db_session):
        job = _mk(service, project)
        done = _run(service.enqueue_job(job.id, project.id, "worker"))
        assert done.status == "queued"
        # dispatch goes through the transactional outbox, not a direct push
        assert queue.pushed == []
        from app.database.models import JobOutboxEvent
        from sqlalchemy import select
        rows = db_session.scalars(
            select(JobOutboxEvent).where(JobOutboxEvent.job_id == job.id)
        ).all()
        assert len(rows) == 1 and rows[0].status == "pending"

    def test_enqueue_twice_conflicts(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        with pytest.raises(ConflictError):
            _run(service.enqueue_job(job.id, project.id, "w"))

    def test_full_lifecycle_via_transition(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        job = service.transition_job(job.id, project.id, "running", "worker")
        assert job.status == "running" and job.attempt_count == 1
        assert job.started_at is not None
        job = service.transition_job(job.id, project.id, "completed", "worker")
        assert job.status == "completed" and job.completed_at is not None

    def test_invalid_transitions(self, service, project):
        job = _mk(service, project)
        with pytest.raises(ConflictError):
            service.transition_job(job.id, project.id, "running", "w")
        with pytest.raises(ConflictError):
            service.transition_job(job.id, project.id, "completed", "w")

    def test_terminal_states_locked(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        service.transition_job(job.id, project.id, "running", "w")
        service.transition_job(job.id, project.id, "completed", "w")
        with pytest.raises(ConflictError):
            service.transition_job(job.id, project.id, "failed", "w")
        with pytest.raises(ConflictError):
            service.cancel_job(job.id, project.id, "w")

    def test_failed_can_requeue(self, service, project, queue, db_session):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        service.transition_job(job.id, project.id, "running", "w")
        job = service.transition_job(
            job.id, project.id, "failed", "w", error="boom"
        )
        assert job.status == "failed" and "boom" in job.last_error
        job = _run(service.enqueue_job(job.id, project.id, "w"))
        assert job.status == "queued"
        from app.database.models import JobOutboxEvent
        from sqlalchemy import select, func
        count = db_session.scalar(
            select(func.count()).select_from(JobOutboxEvent)
            .where(JobOutboxEvent.job_id == job.id)
        )
        assert count == 2


class TestCancellation:
    def test_cancel_pending(self, service, project):
        job = _mk(service, project)
        job = service.cancel_job(job.id, project.id, "user")
        assert job.status == "cancelled"

    def test_cancel_queued(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        job = service.cancel_job(job.id, project.id, "user")
        assert job.status == "cancelled"

    def test_cannot_cancel_running(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        service.transition_job(job.id, project.id, "running", "w")
        with pytest.raises(ConflictError):
            service.cancel_job(job.id, project.id, "user")


class TestAuditHistory:
    def test_events_recorded(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        service.transition_job(job.id, project.id, "running", "w")
        events = service.get_events(job.id, project.id)
        types = [e.event_type for e in events]
        assert types == ["created", "queued", "started"]
        assert [e.seq for e in events] == [1, 2, 3]
        assert events[0].from_status is None
        assert events[0].to_status == "pending"
        assert events[2].actor == "w"

    def test_events_cross_project_404(self, service, project, other_project):
        job = _mk(service, project)
        with pytest.raises(NotFoundError):
            service.get_events(job.id, other_project.id)


class TestQueueFailure:
    def test_enqueue_queue_down_still_queues_via_outbox(self, db_session, project):
        """Outbox decouples enqueue from Redis availability."""
        svc = JobService(db_session, queue=FakeQueue(fail=True))
        job = _mk(svc, project)
        done = _run(svc.enqueue_job(job.id, project.id, "w"))
        assert done.status == "queued"


class TestEligibleJobs:
    def test_queue_eligible_filters(self, service, project):
        due = _mk(service, project)
        future = _mk(
            service, project,
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        eligible = service.queue_eligible_jobs(project.id)
        ids = {j.id for j in eligible}
        assert due.id in ids and future.id not in ids

    def test_queued_job_not_eligible(self, service, project):
        job = _mk(service, project)
        _run(service.enqueue_job(job.id, project.id, "w"))
        assert all(j.id != job.id for j in service.queue_eligible_jobs(project.id))


# ── API tests ────────────────────────────────────────────────────────────


@pytest.fixture
def test_app():
    import os
    os.environ.pop("UGA_API_KEY", None)
    from httpx import ASGITransport, AsyncClient  # noqa
    from app.api.dependencies import get_db_session, get_job_queue
    from app.core.config import Settings
    from app.main import create_app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    fake = FakeQueue()

    async def fake_queue_dep():
        return fake

    app = create_app(Settings(_env_file=None, environment="test", database_url=None, redis_url=None))
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_job_queue] = lambda: fake
    app.state.test_session_factory = session_factory
    yield app, fake
    Base.metadata.drop_all(bind=engine)


def test_job_api_flow(test_app):
    async def run():
        app, fake = test_app
        async with app.router.lifespan_context(app):
            from httpx import ASGITransport, AsyncClient

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                p = await client.post("/api/v1/projects", json={"name": "Job API"})
                pid = p.json()["id"]

                r = await client.post(
                    f"/api/v1/projects/{pid}/jobs",
                    json={"job_type": "growth.evaluate", "payload": {"x": 1}, "idempotency_key": "k"},
                )
                assert r.status_code == 201, r.text
                jid = r.json()["id"]
                assert r.json()["status"] == "pending"

                # idempotent replay
                r2 = await client.post(
                    f"/api/v1/projects/{pid}/jobs",
                    json={"job_type": "growth.evaluate", "idempotency_key": "k"},
                )
                assert r2.json()["id"] == jid

                # list
                lst = await client.get(f"/api/v1/projects/{pid}/jobs")
                assert lst.json()["total"] == 1

                # get
                g = await client.get(f"/api/v1/projects/{pid}/jobs/{jid}")
                assert g.status_code == 200

                # validation error: bad status filter → 422, bad payload → 422
                bad = await client.get(f"/api/v1/projects/{pid}/jobs?status=bogus")
                assert bad.status_code == 422
                bad2 = await client.post(
                    f"/api/v1/projects/{pid}/jobs", json={"job_type": ""}
                )
                assert bad2.status_code == 422

                # enqueue
                en = await client.post(f"/api/v1/projects/{pid}/jobs/{jid}/enqueue")
                assert en.status_code == 200, en.text
                assert en.json()["status"] == "queued"
                # dispatch is via transactional outbox, not a direct push
                from app.database.models import JobOutboxEvent
                from sqlalchemy import select as _sel
                # verify through a fresh session on the same engine
                s = app.state.test_session_factory()
                try:
                    ob = s.scalar(
                        _sel(JobOutboxEvent).where(JobOutboxEvent.job_id == jid)
                    )
                    assert ob is not None and ob.status == "pending"
                finally:
                    s.close()

                # enqueue again → 409
                en2 = await client.post(f"/api/v1/projects/{pid}/jobs/{jid}/enqueue")
                assert en2.status_code == 409

                # events
                ev = await client.get(f"/api/v1/projects/{pid}/jobs/{jid}/events")
                assert [e["event_type"] for e in ev.json()] == ["created", "queued"]

                # cancel queued job
                cx = await client.post(f"/api/v1/projects/{pid}/jobs/{jid}/cancel")
                assert cx.status_code == 200 and cx.json()["status"] == "cancelled"

                # 404 cross-project
                p2 = await client.post("/api/v1/projects", json={"name": "Other"})
                nf = await client.get(f"/api/v1/projects/{p2.json()['id']}/jobs/{jid}")
                assert nf.status_code == 404

    asyncio.run(run())


class TestProjectDeletionBlockers:
    def test_job_blocks_project_delete(self, db_session, project, service):
        _mk(service, project)
        ps = ProjectService(db_session)
        from app.core.errors import ConflictError as CE
        with pytest.raises(CE) as ei:
            ps.delete_project(project.id, owner=None)
        assert ei.value.code == "cannot_delete_audited_project"
        assert "job" in str(ei.value).lower()

    def test_project_without_jobs_deletes(self, db_session, other_project):
        ps = ProjectService(db_session)
        ps.delete_project(other_project.id, owner=None)
        from sqlalchemy import select as sel
        assert db_session.scalar(sel(Project).where(Project.id == other_project.id)) is None
