"""PostgreSQL concurrency tests for Phase 6 integration execution.

Runs only against UGA_TEST_DATABASE_URL (dedicated test database). Uses real
committed rows and independent sessions/threads to verify that row locking
prevents double execution and that the shared rate limit holds across
concurrent workers. All created rows are deleted in teardown.
"""

import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import ConflictError, RateLimitError
from app.database.models import (
    IntegrationAction,
    IntegrationActionEvent,
    IntegrationCallLog,
    IntegrationProvider,
    Project,
)
from app.schemas.integration import IntegrationActionCreate, IntegrationProviderCreate
from app.schemas.project import ProjectCreate
from app.services.integration import IntegrationService
from app.services.project import ProjectService


def _get_pg_test_url() -> str | None:
    raw = os.getenv("UGA_TEST_DATABASE_URL", "").strip()
    if not raw or not raw.startswith("postgresql"):
        return None
    return raw


PG_TEST_URL = _get_pg_test_url()

pytestmark = pytest.mark.skipif(
    PG_TEST_URL is None,
    reason="UGA_TEST_DATABASE_URL is not configured (dedicated test database required)",
)


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_TEST_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)


def _svc(session):
    return IntegrationService(session, credential_codec=None, approval_ttl_seconds=3600)


def _setup_project_provider(session_factory, rate_limit=60):
    """Create committed project + provider; returns ids for teardown."""
    s = session_factory()
    try:
        project = ProjectService(s).create_project(
            ProjectCreate(name=f"pg-concurrency-{uuid.uuid4().hex[:8]}")
        )
        provider = _svc(s).create_provider(
            IntegrationProviderCreate(
                name="pg-sandbox", adapter_type="sandbox",
                rate_limit_per_minute=rate_limit,
            ),
            project_id=project.id,
        )
        s.commit()
        return project.id, provider.id
    finally:
        s.close()


def _make_approved_action(session_factory, project_id, provider_id, key=None):
    s = session_factory()
    try:
        svc = _svc(s)
        action, _ = svc.create_action(
            provider_id,
            IntegrationActionCreate(
                action_type="t", payload={"x": 1}, idempotency_key=key
            ),
            project_id=project_id,
            actor="setup",
        )
        svc.approve(action.id, project_id, "approver", None)
        s.commit()
        return action.id
    finally:
        s.close()


def _teardown(session_factory, project_id, provider_id):
    s = session_factory()
    try:
        action_ids = select(IntegrationAction.id).where(
            IntegrationAction.project_id == project_id
        )
        s.execute(
            delete(IntegrationCallLog).where(
                IntegrationCallLog.action_id.in_(action_ids)
            )
        )
        s.execute(
            delete(IntegrationActionEvent).where(
                IntegrationActionEvent.action_id.in_(action_ids)
            )
        )
        s.execute(
            delete(IntegrationAction).where(
                IntegrationAction.project_id == project_id
            )
        )
        s.execute(
            delete(IntegrationProvider).where(
                IntegrationProvider.id == provider_id
            )
        )
        s.execute(delete(Project).where(Project.id == project_id))
        s.commit()
    finally:
        s.close()


def test_concurrent_execute_runs_action_exactly_once(session_factory):
    project_id, provider_id = _setup_project_provider(session_factory)
    action_id = _make_approved_action(session_factory, project_id, provider_id)
    results: list[str] = []
    lock = threading.Lock()

    def worker():
        s = session_factory()
        try:
            _svc(s).execute(action_id, project_id, "worker")
            with lock:
                results.append("succeeded")
        except ConflictError:
            with lock:
                results.append("conflict")
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(results) == ["conflict", "conflict", "conflict", "succeeded"]

    s = session_factory()
    try:
        action = s.get(IntegrationAction, action_id)
        assert action.status == "succeeded"
        assert action.attempt_count == 1
        logs = s.scalars(
            select(IntegrationCallLog).where(IntegrationCallLog.action_id == action_id)
        ).all()
        assert len(logs) == 1
    finally:
        s.close()
        _teardown(session_factory, project_id, provider_id)


def test_concurrent_idempotent_create_returns_single_action(session_factory):
    project_id, provider_id = _setup_project_provider(session_factory)
    key = f"idem-{uuid.uuid4().hex[:8]}"
    created_ids: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker():
        s = session_factory()
        try:
            action, created = _svc(s).create_action(
                provider_id,
                IntegrationActionCreate(
                    action_type="t", payload={"x": 1}, idempotency_key=key
                ),
                project_id=project_id,
                actor="worker",
            )
            with lock:
                created_ids.append(action.id)
        except Exception as exc:  # noqa: BLE001 - record for assertion
            with lock:
                errors.append(exc)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors
    assert len(set(created_ids)) == 1

    s = session_factory()
    try:
        count = len(
            s.scalars(
                select(IntegrationAction).where(
                    IntegrationAction.provider_id == provider_id,
                    IntegrationAction.idempotency_key == key,
                )
            ).all()
        )
        assert count == 1
    finally:
        s.close()
        _teardown(session_factory, project_id, provider_id)


def test_rate_limit_boundary_under_concurrency(session_factory):
    project_id, provider_id = _setup_project_provider(session_factory, rate_limit=3)
    action_ids = [
        _make_approved_action(session_factory, project_id, provider_id)
        for _ in range(6)
    ]
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(aid):
        s = session_factory()
        try:
            _svc(s).execute(aid, project_id, "worker")
            with lock:
                outcomes.append("succeeded")
        except RateLimitError:
            with lock:
                outcomes.append("rate_limited")
        except ConflictError:
            with lock:
                outcomes.append("conflict")
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(aid,)) for aid in action_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert outcomes.count("succeeded") == 3
    assert outcomes.count("rate_limited") == 3

    s = session_factory()
    try:
        logs = s.scalars(
            select(IntegrationCallLog).where(
                IntegrationCallLog.provider_id == provider_id
            )
        ).all()
        assert len(logs) == 3
    finally:
        s.close()
        _teardown(session_factory, project_id, provider_id)
