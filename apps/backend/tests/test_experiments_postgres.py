"""PostgreSQL concurrency tests for Phase 7 experiment transitions.

Runs only against UGA_TEST_DATABASE_URL. Verifies that concurrent lifecycle
transitions on the same experiment serialize on the row lock, producing
unique monotonic history seq values with no server errors.
"""

import os
import threading
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import ConflictError
from app.database.models import (
    Experiment,
    ExperimentEvaluation,
    ExperimentOutcome,
    ExperimentStatusHistory,
    GrowthStrategy,
    LearningRecord,
    Project,
)
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentTransition,
    SuccessCriteria,
    SuccessCriterion,
)
from app.schemas.project import ProjectCreate
from app.schemas.strategy import GrowthStrategyCreate
from app.services.experiment import ExperimentService
from app.services.project import ProjectService
from app.services.strategy import StrategyService


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
    return ExperimentService(session)


def _setup(session_factory):
    """Committed project + strategy + experiment in 'in_review'."""
    s = session_factory()
    try:
        project = ProjectService(s).create_project(
            ProjectCreate(name=f"pg-exp-{uuid.uuid4().hex[:8]}")
        )
        strategy = StrategyService(s).create_strategy(
            GrowthStrategyCreate(
                name="S", strategic_vision="v", target_audience="u",
                time_horizon="q",
            ),
            project_id=project.id,
            actor="setup",
        )
        svc = _svc(s)
        exp = svc.create_experiment(
            strategy.id,
            ExperimentCreate(
                name="E",
                success_criteria=SuccessCriteria(
                    criteria=[
                        SuccessCriterion(
                            metric_name="m", comparator="gte", threshold=1.0
                        )
                    ]
                ),
            ),
            project_id=project.id,
            actor="setup",
        )
        svc.transition_experiment(
            exp.id, strategy.id,
            ExperimentTransition(status="in_review"), project.id, "setup",
        )
        s.commit()
        return project.id, strategy.id, exp.id
    finally:
        s.close()


def _teardown(session_factory, project_id):
    s = session_factory()
    try:
        exp_ids = select(Experiment.id).where(Experiment.project_id == project_id)
        s.execute(
            delete(ExperimentEvaluation).where(
                ExperimentEvaluation.experiment_id.in_(exp_ids)
            )
        )
        s.execute(
            delete(ExperimentOutcome).where(
                ExperimentOutcome.experiment_id.in_(exp_ids)
            )
        )
        s.execute(
            delete(ExperimentStatusHistory).where(
                ExperimentStatusHistory.experiment_id.in_(exp_ids)
            )
        )
        s.execute(delete(LearningRecord).where(LearningRecord.project_id == project_id))
        s.execute(delete(Experiment).where(Experiment.project_id == project_id))
        s.execute(delete(GrowthStrategy).where(GrowthStrategy.project_id == project_id))
        s.execute(delete(Project).where(Project.id == project_id))
        s.commit()
    finally:
        s.close()


def test_concurrent_transitions_serialize_with_unique_seq(session_factory):
    project_id, strategy_id, exp_id = _setup(session_factory)
    results: list[str] = []
    lock = threading.Lock()

    def worker(target: str, reason: str | None = None):
        s = session_factory()
        try:
            _svc(s).transition_experiment(
                exp_id, strategy_id,
                ExperimentTransition(status=target, reason=reason),
                project_id, "worker",
            )
            with lock:
                results.append("ok")
        except ConflictError:
            with lock:
                results.append("conflict")
        finally:
            s.close()

    # in_review -> running vs in_review -> draft are mutually exclusive:
    # whichever commits first leaves the other target invalid.
    reason = "Returning to draft for more design work"
    threads = [
        threading.Thread(target=worker, args=("running",)),
        threading.Thread(target=worker, args=("draft", reason)),
        threading.Thread(target=worker, args=("running",)),
        threading.Thread(target=worker, args=("draft", reason)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert results.count("ok") == 1
    assert results.count("conflict") == 3

    s = session_factory()
    try:
        history = s.scalars(
            select(ExperimentStatusHistory)
            .where(ExperimentStatusHistory.experiment_id == exp_id)
            .order_by(ExperimentStatusHistory.seq)
        ).all()
        seqs = [h.seq for h in history]
        assert seqs == sorted(seqs)
        assert len(seqs) == len(set(seqs)) == 3  # draft, in_review, winner
        statuses = [(h.previous_status, h.new_status) for h in history]
        assert statuses[0] == (None, "draft")
        assert statuses[1] == ("draft", "in_review")
        assert statuses[2][0] == "in_review"
        assert statuses[2][1] in {"running", "draft"}
    finally:
        s.close()
        _teardown(session_factory, project_id)


def test_concurrent_same_target_transitions(session_factory):
    """Two workers racing in_review->running: one wins, one conflicts."""
    project_id, strategy_id, exp_id = _setup(session_factory)
    results: list[str] = []
    lock = threading.Lock()

    def worker():
        s = session_factory()
        try:
            _svc(s).transition_experiment(
                exp_id, strategy_id,
                ExperimentTransition(status="running"), project_id, "worker",
            )
            with lock:
                results.append("ok")
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

    assert results.count("ok") == 1
    assert results.count("conflict") == 3

    s = session_factory()
    try:
        history = s.scalars(
            select(ExperimentStatusHistory)
            .where(ExperimentStatusHistory.experiment_id == exp_id)
            .order_by(ExperimentStatusHistory.seq)
        ).all()
        assert len(history) == 3
        assert [h.seq for h in history] == [1, 2, 3]
        exp = s.get(Experiment, exp_id)
        assert exp.status == "running"
        assert exp.started_at is not None
    finally:
        s.close()
        _teardown(session_factory, project_id)
