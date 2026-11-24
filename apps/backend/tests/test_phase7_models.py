"""Phase 7 Milestone 1 — model and database constraint tests (SQLite)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import (
    Base,
    Experiment,
    ExperimentEvaluation,
    ExperimentOutcome,
    ExperimentStatusHistory,
    LearningRecord,
    Project,
    StrategyGoal,
    GrowthStrategy,
)
from app.schemas.project import ProjectCreate
from app.schemas.strategy import GrowthStrategyCreate
from app.services.project import ProjectService
from app.services.strategy import StrategyService


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
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="P7"))


@pytest.fixture
def strategy(db_session, project):
    return StrategyService(db_session).create_strategy(
        GrowthStrategyCreate(
            name="S7", strategic_vision="V", target_audience="A", time_horizon="Q1"
        ),
        project_id=project.id,
        actor="test",
    )


def _experiment(db_session, project, strategy, goal=None, **kw):
    exp = Experiment(
        id=kw.pop("id", "exp-1"),
        project_id=project.id,
        strategy_id=strategy.id,
        goal_id=goal.id if goal else None,
        name=kw.pop("name", "Exp"),
        hypothesis="H",
        status=kw.pop("status", "draft"),
        **kw,
    )
    db_session.add(exp)
    db_session.commit()
    return exp


class TestExperimentModel:
    def test_create_with_strategy(self, db_session, project, strategy):
        exp = _experiment(db_session, project, strategy)
        assert exp.status == "draft"
        assert exp.project_id == project.id
        assert exp.strategy_id == strategy.id

    def test_create_with_goal_reference(self, db_session, project, strategy):
        from app.schemas.goal import StrategyGoalCreate
        from app.services.goal import GoalService

        goal = GoalService(db_session).create_goal(
            strategy.id,
            StrategyGoalCreate(
                name="G", metric_name="m", metric_unit="u",
                baseline_value=0.0, target_value=10.0,
            ),
            project_id=project.id,
            actor="test",
        )
        exp = _experiment(db_session, project, strategy, goal=goal)
        assert exp.goal_id == goal.id

    def test_invalid_status_rejected_by_check(self, db_session, project, strategy):
        exp = Experiment(
            id="bad", project_id=project.id, strategy_id=strategy.id,
            name="X", status="bogus",
        )
        db_session.add(exp)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_cross_project_strategy_fk_rejected(self, db_session, project, strategy):
        other = ProjectService(db_session).create_project(ProjectCreate(name="Other"))
        exp = Experiment(
            id="xproj", project_id=other.id, strategy_id=strategy.id, name="X"
        )
        db_session.add(exp)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_experiment_cascades_with_strategy(self, db_session, project, strategy):
        exp = _experiment(db_session, project, strategy)
        # strategy_goals-style CASCADE: deleting the strategy removes experiments
        exp_id = exp.id
        db_session.delete(strategy)
        db_session.commit()
        assert db_session.get(Experiment, exp_id) is None


class TestAuditTables:
    def test_status_history_records_and_restrict(self, db_session, project, strategy):
        exp = _experiment(db_session, project, strategy)
        hist = ExperimentStatusHistory(
            id="h1", experiment_id=exp.id, project_id=project.id,
            previous_status=None, new_status="draft", actor="test",
        )
        db_session.add(hist)
        db_session.commit()
        # RESTRICT: cannot delete experiment while history exists
        db_session.delete(exp)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_outcome_append_only_restricts_experiment_delete(
        self, db_session, project, strategy
    ):
        from datetime import datetime, timezone

        exp = _experiment(db_session, project, strategy, status="running")
        outcome = ExperimentOutcome(
            id="o1", experiment_id=exp.id, project_id=project.id,
            metric_name="m", value=1.5, sample_size=100,
            observed_at=datetime.now(timezone.utc), source="manual", actor="test",
        )
        db_session.add(outcome)
        db_session.commit()
        db_session.delete(exp)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_evaluation_verdict_check_and_restrict(
        self, db_session, project, strategy
    ):
        from datetime import datetime, timezone

        exp = _experiment(db_session, project, strategy, status="completed")
        ev = ExperimentEvaluation(
            id="e1", experiment_id=exp.id, project_id=project.id,
            verdict="succeeded",
            evaluated_at=datetime.now(timezone.utc), actor="test",
        )
        db_session.add(ev)
        db_session.commit()
        db_session.delete(exp)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_verdict_rejected(self, db_session, project, strategy):
        from datetime import datetime, timezone

        exp = _experiment(db_session, project, strategy)
        ev = ExperimentEvaluation(
            id="e2", experiment_id=exp.id, project_id=project.id,
            verdict="maybe", evaluated_at=datetime.now(timezone.utc), actor="t",
        )
        db_session.add(ev)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_outcome_source_rejected(self, db_session, project, strategy):
        from datetime import datetime, timezone

        exp = _experiment(db_session, project, strategy)
        o = ExperimentOutcome(
            id="o2", experiment_id=exp.id, project_id=project.id,
            metric_name="m", value=1.0, observed_at=datetime.now(timezone.utc),
            source="ai_guess", actor="t",
        )
        db_session.add(o)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestLearningRecord:
    def test_create_candidate(self, db_session, project, strategy):
        lr = LearningRecord(
            id="l1", project_id=project.id, strategy_id=strategy.id,
            title="T", insight="I", status="candidate",
        )
        db_session.add(lr)
        db_session.commit()
        assert lr.status == "candidate"

    def test_learning_restricts_experiment_delete(self, db_session, project, strategy):
        exp = _experiment(db_session, project, strategy)
        lr = LearningRecord(
            id="l2", project_id=project.id, experiment_id=exp.id,
            title="T", insight="I", status="validated",
        )
        db_session.add(lr)
        db_session.commit()
        db_session.delete(exp)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_learning_status_rejected(self, db_session, project):
        lr = LearningRecord(
            id="l3", project_id=project.id, title="T", insight="I", status="bogus"
        )
        db_session.add(lr)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_learning_requires_project(self, db_session):
        lr = LearningRecord(
            id="l4", project_id="nonexistent", title="T", insight="I"
        )
        db_session.add(lr)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
