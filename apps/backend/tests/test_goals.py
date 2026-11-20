from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError
from app.database.models import Base
from app.schemas.goal import (
    GoalMetricUpdateCreate,
    StrategyGoalCreate,
    StrategyGoalUpdate,
    compute_goal_progress,
)
from app.schemas.project import ProjectCreate
from app.schemas.strategy import GrowthStrategyCreate
from app.services.goal import GoalService
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
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def project(db_session):
    p_service = ProjectService(db_session)
    return p_service.create_project(ProjectCreate(name="Goals Test Project"))


@pytest.fixture
def strategy(db_session, project):
    s_service = StrategyService(db_session)
    return s_service.create_strategy(
        GrowthStrategyCreate(
            name="Goals Parent Strategy",
            strategic_vision="Parent Vision",
            target_audience="Target Users",
            time_horizon="Q1_2027",
        ),
        project_id=project.id,
        actor="admin",
    )


class TestGoalProgressFormulas:
    def test_increasing_metric_progress(self):
        # Baseline: 10%, Target: 20%, Current: 15% -> 50% progress
        progress, is_increasing = compute_goal_progress(baseline=10.0, target=20.0, current=15.0)
        assert is_increasing is True
        assert progress == 50.0

        # Current: 20% -> 100% progress
        progress, _ = compute_goal_progress(baseline=10.0, target=20.0, current=20.0)
        assert progress == 100.0

        # Current: 25% -> 150% progress (exceeded)
        progress, _ = compute_goal_progress(baseline=10.0, target=20.0, current=25.0)
        assert progress == 150.0

    def test_decreasing_metric_progress(self):
        # E.g. Churn rate: Baseline 5.0%, Target 1.0%, Current 3.0%
        # Span = 4.0, improvement = 5.0 - 3.0 = 2.0 -> 50% progress
        progress, is_increasing = compute_goal_progress(baseline=5.0, target=1.0, current=3.0)
        assert is_increasing is False
        assert progress == 50.0

        # Current: 1.0% -> 100% progress
        progress, _ = compute_goal_progress(baseline=5.0, target=1.0, current=1.0)
        assert progress == 100.0

        # Current: 0.5% -> 112.5% progress
        progress, _ = compute_goal_progress(baseline=5.0, target=1.0, current=0.5)
        assert progress == 112.5

        # Regression: Churn rose to 6.0% -> -25% progress
        progress, _ = compute_goal_progress(baseline=5.0, target=1.0, current=6.0)
        assert progress == -25.0

    def test_flat_metric_division_by_zero_safety(self):
        # Baseline == Target
        progress, is_increasing = compute_goal_progress(baseline=100.0, target=100.0, current=100.0)
        assert is_increasing is True
        assert progress == 100.0

        progress, _ = compute_goal_progress(baseline=100.0, target=100.0, current=95.0)
        assert progress == 0.0


class TestGoalCRUDAndProgressService:
    def test_create_and_get_goal(self, db_session, project, strategy):
        service = GoalService(db_session)
        deadline = datetime.now(timezone.utc) + timedelta(days=90)
        goal = service.create_goal(
            strategy.id,
            StrategyGoalCreate(
                name="Double 7-Day Student Retention",
                description="Improve Day-7 retention from 12% to 24%",
                metric_name="d7_retention_pct",
                metric_unit="percent",
                baseline_value=12.0,
                target_value=24.0,
                deadline=deadline,
            ),
            project_id=project.id,
        )

        assert goal.id is not None
        assert goal.strategy_id == strategy.id
        assert float(goal.baseline_value) == 12.0
        assert float(goal.current_value) == 12.0  # Defaults to baseline
        assert float(goal.target_value) == 24.0
        assert goal.status == "pending"

    def test_atomic_progress_update_and_history(self, db_session, project, strategy):
        service = GoalService(db_session)
        goal = service.create_goal(
            strategy.id,
            StrategyGoalCreate(
                name="Quick Apply Submissions",
                metric_name="daily_applications",
                metric_unit="count",
                baseline_value=100.0,
                target_value=500.0,
            ),
            project_id=project.id,
        )

        # Record progress check-in #1
        updated_goal, update_rec1 = service.record_progress(
            goal.id,
            GoalMetricUpdateCreate(
                new_value=250.0,
                notes="Week 2 check-in: Resume caching rolled out to 25% cohort",
            ),
            project_id=project.id,
            actor="pm-student-growth",
        )

        assert float(updated_goal.current_value) == 250.0
        assert updated_goal.status == "on_track"
        assert float(update_rec1.previous_value) == 100.0
        assert float(update_rec1.new_value) == 250.0
        assert update_rec1.actor == "pm-student-growth"

        # Record progress check-in #2: goal achieved
        achieved_goal, update_rec2 = service.record_progress(
            goal.id,
            GoalMetricUpdateCreate(
                new_value=520.0,
                notes="Target exceeded following university partner job fair",
            ),
            project_id=project.id,
            actor="growth-analyst",
        )

        assert float(achieved_goal.current_value) == 520.0
        assert achieved_goal.status == "achieved"

        # Verify history retrieval
        history = service.get_metric_history(goal.id, project_id=project.id)
        assert len(history) == 2
        assert float(history[0].new_value) == 520.0  # Most recent first
        assert float(history[1].new_value) == 250.0

    def test_goal_deletion_prohibited_when_metric_history_exists(self, db_session, project, strategy):
        service = GoalService(db_session)
        goal = service.create_goal(
            strategy.id,
            StrategyGoalCreate(
                name="Protected Goal",
                metric_name="metric",
                metric_unit="unit",
                baseline_value=1.0,
                target_value=10.0,
            ),
            project_id=project.id,
        )

        # Before any metric updates, goal can be deleted
        service.delete_goal(goal.id, project_id=project.id)
        with pytest.raises(NotFoundError):
            service.get_goal(goal.id, project_id=project.id)

        # Create new goal and add progress
        goal2 = service.create_goal(
            strategy.id,
            StrategyGoalCreate(
                name="Protected Goal 2",
                metric_name="metric",
                metric_unit="unit",
                baseline_value=1.0,
                target_value=10.0,
            ),
            project_id=project.id,
        )
        service.record_progress(
            goal2.id,
            GoalMetricUpdateCreate(new_value=5.0, notes="Check-in"),
            project_id=project.id,
            actor="lead",
        )

        # Deleting goal with metric updates must be prohibited
        with pytest.raises(ConflictError, match="cannot be deleted"):
            service.delete_goal(goal2.id, project_id=project.id)
