"""PostgreSQL constraint tests for Phase 7 models.

Runs only against UGA_TEST_DATABASE_URL. Verifies composite foreign keys and
RESTRICT audit protections on real PostgreSQL. Uses the external-transaction
savepoint pattern — nothing persists.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import (
    Experiment,
    ExperimentEvaluation,
    ExperimentOutcome,
    ExperimentStatusHistory,
    GrowthStrategy,
    LearningRecord,
    Project,
    StrategyGoal,
)


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
def pg_session(pg_engine):
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        autocommit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _mk_project(session):
    p = Project(id=str(uuid.uuid4()), name="pg7", slug=f"pg7-{uuid.uuid4().hex[:8]}", owner="test")
    session.add(p)
    session.flush()
    return p


def _mk_strategy(session, project):
    s = GrowthStrategy(
        id=str(uuid.uuid4()), project_id=project.id, name="S",
        strategic_vision="V", target_audience="A", time_horizon="Q1",
        status="draft", slug=f"s-{uuid.uuid4().hex[:8]}",
    )
    session.add(s)
    session.flush()
    return s


def _mk_experiment(session, project, strategy, goal=None):
    e = Experiment(
        id=str(uuid.uuid4()), project_id=project.id, strategy_id=strategy.id,
        goal_id=goal.id if goal else None, name="E", status="draft",
    )
    session.add(e)
    session.flush()
    return e


def test_pg_composite_fk_rejects_cross_project_strategy(pg_session):
    p1 = _mk_project(pg_session)
    p2 = _mk_project(pg_session)
    s1 = _mk_strategy(pg_session, p1)
    # experiment claims p2 but strategy belongs to p1 -> composite FK violation
    e = Experiment(
        id=str(uuid.uuid4()), project_id=p2.id, strategy_id=s1.id, name="X"
    )
    pg_session.add(e)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_restrict_blocks_experiment_delete_with_outcome(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    e = _mk_experiment(pg_session, p, s)
    o = ExperimentOutcome(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        metric_name="m", value=1.0, observed_at=datetime.now(timezone.utc),
        source="manual", actor="t",
    )
    pg_session.add(o)
    pg_session.flush()
    pg_session.delete(e)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_learning_restricts_via_experiment_fk(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    e = _mk_experiment(pg_session, p, s)
    lr = LearningRecord(
        id=str(uuid.uuid4()), project_id=p.id, experiment_id=e.id,
        title="T", insight="I", status="candidate",
    )
    pg_session.add(lr)
    pg_session.flush()
    pg_session.delete(e)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_goal_reference_enforced(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    goal = StrategyGoal(
        id=str(uuid.uuid4()), project_id=p.id, strategy_id=s.id,
        name="G", metric_name="m", metric_unit="u",
        baseline_value=0.0, target_value=1.0, current_value=0.0,
        status="pending",
    )
    pg_session.add(goal)
    pg_session.flush()
    e = _mk_experiment(pg_session, p, s, goal=goal)
    assert e.goal_id == goal.id
    # bogus goal id -> FK violation
    bad = Experiment(
        id=str(uuid.uuid4()), project_id=p.id, strategy_id=s.id,
        goal_id=str(uuid.uuid4()), name="bad",
    )
    pg_session.add(bad)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_status_history_restrict(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    e = _mk_experiment(pg_session, p, s)
    h = ExperimentStatusHistory(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        previous_status=None, new_status="draft", actor="t",
    )
    pg_session.add(h)
    pg_session.flush()
    pg_session.delete(e)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_supersedes_self_fk_enforced(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    e = _mk_experiment(pg_session, p, s)
    now = datetime.now(timezone.utc)
    o1 = ExperimentOutcome(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        metric_name="m", value=1.0, observed_at=now, source="manual", actor="t",
    )
    pg_session.add(o1)
    pg_session.flush()
    # valid supersession
    o2 = ExperimentOutcome(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        metric_name="m", value=2.0, observed_at=now, source="manual", actor="t",
        supersedes_id=o1.id,
    )
    pg_session.add(o2)
    pg_session.flush()
    assert o2.supersedes_id == o1.id
    # bogus supersedes target -> FK violation
    bad = ExperimentOutcome(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        metric_name="m", value=3.0, observed_at=now, source="manual", actor="t",
        supersedes_id=str(uuid.uuid4()),
    )
    pg_session.add(bad)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_restrict_blocks_superseded_outcome_delete(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    e = _mk_experiment(pg_session, p, s)
    now = datetime.now(timezone.utc)
    o1 = ExperimentOutcome(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        metric_name="m", value=1.0, observed_at=now, source="manual", actor="t",
    )
    pg_session.add(o1)
    pg_session.flush()
    o2 = ExperimentOutcome(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        metric_name="m", value=2.0, observed_at=now, source="manual", actor="t",
        supersedes_id=o1.id,
    )
    pg_session.add(o2)
    pg_session.flush()
    pg_session.delete(o1)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_pg_evaluation_restrict(pg_session):
    p = _mk_project(pg_session)
    s = _mk_strategy(pg_session, p)
    e = _mk_experiment(pg_session, p, s)
    ev = ExperimentEvaluation(
        id=str(uuid.uuid4()), experiment_id=e.id, project_id=p.id,
        verdict="inconclusive", evaluated_at=datetime.now(timezone.utc), actor="t",
    )
    pg_session.add(ev)
    pg_session.flush()
    pg_session.delete(e)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()
