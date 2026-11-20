import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import (
    Base,
    GrowthOpportunity,
    GrowthStrategy,
    OpportunityStatusHistory,
    Project,
    StrategyGoal,
    StrategyOpportunityAssociation,
    StrategyStatusHistory,
)
from app.schemas.opportunity import OpportunityCreate
from app.schemas.project import ProjectCreate
from app.schemas.strategy import (
    GrowthStrategyCreate,
    GrowthStrategyTransition,
    GrowthStrategyUpdate,
)
from app.schemas.strategy_association import StrategyOpportunityAssociateItem
from app.services.opportunity import OpportunityService
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
    return p_service.create_project(ProjectCreate(name="Strategy Test Project"))


class TestStrategySchemaValidation:
    def test_valid_strategy_create(self):
        strat = GrowthStrategyCreate(
            name="Q1 Activation Overhaul",
            strategic_vision="Streamline first-session UX to double activation",
            target_audience="University students on mobile",
            strategic_constraints="No paid acquisition; stay within brand safety guidelines",
            budget_envelope=5000.0,
            currency="USD",
            time_horizon="Q1_2027",
        )
        assert strat.name == "Q1 Activation Overhaul"
        assert strat.currency == "USD"
        assert strat.budget_envelope == 5000.0

    def test_currency_normalized_to_uppercase(self):
        strat = GrowthStrategyCreate(
            name="Euro Strategy",
            strategic_vision="Expand to EU",
            target_audience="EU students",
            currency="eur",
            time_horizon="H1_2027",
        )
        assert strat.currency == "EUR"

    def test_invalid_currency_rejected(self):
        with pytest.raises(ValidationError):
            GrowthStrategyCreate(
                name="Bad Currency",
                strategic_vision="Vision",
                target_audience="Audience",
                currency="US",  # Too short
                time_horizon="Q1",
            )

        with pytest.raises(ValidationError):
            GrowthStrategyCreate(
                name="Bad Currency",
                strategic_vision="Vision",
                target_audience="Audience",
                currency="USDD",  # Too long
                time_horizon="Q1",
            )

        with pytest.raises(ValidationError):
            GrowthStrategyCreate(
                name="Bad Currency",
                strategic_vision="Vision",
                target_audience="Audience",
                currency="123",  # Non-alphabetical
                time_horizon="Q1",
            )

    def test_negative_budget_rejected(self):
        with pytest.raises(ValidationError):
            GrowthStrategyCreate(
                name="Negative Budget",
                strategic_vision="Vision",
                target_audience="Audience",
                budget_envelope=-100.0,
                time_horizon="Q1",
            )

    def test_invalid_slug_format_rejected(self):
        with pytest.raises(ValidationError):
            GrowthStrategyCreate(
                name="Bad Slug",
                slug="Invalid Slug With Spaces",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            )


class TestStrategyLifecycleAndHistory:
    def test_newly_created_draft_has_no_history_records_until_transition(
        self, db_session, project
    ):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Spring Campus Launch",
                strategic_vision="Deploy student ambassador network across 5 campuses",
                target_audience="Campus freshmen",
                budget_envelope=2500.0,
                currency="USD",
                time_horizon="Spring_2027",
            ),
            project_id=project.id,
            actor="growth-lead",
        )

        assert strat.id is not None
        assert strat.status == "draft"
        assert strat.slug == "spring-campus-launch"

        # Newly created draft has no lifecycle-history records
        history = service.get_history(strat.id, project_id=project.id)
        assert len(history) == 0

        # First transition creates the first history record
        t1 = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="in_review"),
            project_id=project.id,
            actor="growth-lead",
        )
        assert t1.status == "in_review"

        history_after = service.get_history(strat.id, project_id=project.id)
        assert len(history_after) == 1
        assert history_after[0].previous_status == "draft"
        assert history_after[0].new_status == "in_review"
        assert history_after[0].actor == "growth-lead"

    def test_allowed_lifecycle_transitions(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Lifecycle Test",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q2",
            ),
            project_id=project.id,
            actor="admin",
        )

        # draft -> in_review
        s1 = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="in_review"),
            project_id=project.id,
            actor="admin",
        )
        assert s1.status == "in_review"

        # in_review -> approved
        s2 = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="approved"),
            project_id=project.id,
            actor="vp-growth",
        )
        assert s2.status == "approved"

        # approved -> active
        s3 = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="active"),
            project_id=project.id,
            actor="growth-lead",
        )
        assert s3.status == "active"

        # active -> completed
        s4 = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="completed"),
            project_id=project.id,
            actor="growth-lead",
        )
        assert s4.status == "completed"

        # completed -> archived (requires reason)
        s5 = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(
                status="archived",
                reason="Strategy completed and Q2 cycle closed successfully",
            ),
            project_id=project.id,
            actor="admin",
        )
        assert s5.status == "archived"

        history = service.get_history(strat.id, project_id=project.id)
        assert len(history) == 5

    def test_invalid_lifecycle_transition_rejected(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Skip Steps",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=project.id,
            actor="admin",
        )

        # Cannot jump from draft to active or completed
        with pytest.raises(ConflictError, match="Cannot transition strategy"):
            service.transition_strategy(
                strat.id,
                GrowthStrategyTransition(status="active"),
                project_id=project.id,
                actor="admin",
            )

        with pytest.raises(ConflictError, match="Cannot transition strategy"):
            service.transition_strategy(
                strat.id,
                GrowthStrategyTransition(status="completed"),
                project_id=project.id,
                actor="admin",
            )

    def test_mandatory_reason_enforced_on_consequential_transitions(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Reversal Test",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=project.id,
            actor="admin",
        )

        # Move to in_review
        service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="in_review"),
            project_id=project.id,
            actor="admin",
        )

        # Reversing in_review -> draft without reason is rejected
        with pytest.raises(UnprocessableEntityError, match="requires an explanatory reason"):
            service.transition_strategy(
                strat.id,
                GrowthStrategyTransition(status="draft"),
                project_id=project.id,
                actor="reviewer",
            )

        # Reason too short (< 10 chars) is rejected
        with pytest.raises(UnprocessableEntityError, match="at least 10 characters"):
            service.transition_strategy(
                strat.id,
                GrowthStrategyTransition(status="draft", reason="Too short"),
                project_id=project.id,
                actor="reviewer",
            )

        # Valid reason succeeds
        reverted = service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(
                status="draft",
                reason="Budget assumptions need revision after finance meeting",
            ),
            project_id=project.id,
            actor="reviewer",
        )
        assert reverted.status == "draft"

    def test_ordinary_update_cannot_bypass_lifecycle_transition(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Status Hack",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=project.id,
            actor="admin",
        )

        with pytest.raises(ConflictError, match="Use the transition endpoint"):
            service.update_strategy(
                strat.id,
                GrowthStrategyUpdate(status="approved"),
                project_id=project.id,
                actor="hacker",
            )


class TestStrategyDeletionRules:
    def test_untransitioned_draft_strategy_can_be_deleted(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Disposable Draft",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=project.id,
            actor="admin",
        )

        # Confirm newly created draft has no history records
        assert service.get_history(strat.id, project_id=project.id) == []

        # Untransitioned draft strategy with no goals/associations can be deleted
        service.delete_strategy(strat.id, project_id=project.id)

        with pytest.raises(NotFoundError):
            service.get_strategy(strat.id, project_id=project.id)

    def test_non_draft_strategy_cannot_be_deleted(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="In Review Strategy",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=project.id,
            actor="admin",
        )
        service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="in_review"),
            project_id=project.id,
            actor="admin",
        )

        with pytest.raises(ConflictError, match="Only draft strategies can be deleted"):
            service.delete_strategy(strat.id, project_id=project.id)

    def test_strategy_with_transition_history_cannot_be_deleted(self, db_session, project):
        service = StrategyService(db_session)
        strat = service.create_strategy(
            GrowthStrategyCreate(
                name="Audited Draft",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=project.id,
            actor="admin",
        )
        # Transition to in_review and back to draft
        service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="in_review"),
            project_id=project.id,
            actor="admin",
        )
        service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(
                status="draft", reason="Returned to draft for further research"
            ),
            project_id=project.id,
            actor="reviewer",
        )

        # Even though status is draft, it has transition history -> delete must be blocked!
        with pytest.raises(ConflictError, match="Strategies with lifecycle transition history cannot be deleted"):
            service.delete_strategy(strat.id, project_id=project.id)

        # Existing history is never deleted by application service operations
        history = service.get_history(strat.id, project_id=project.id)
        assert len(history) == 2
        assert history[0].new_status == "in_review"
        assert history[1].new_status == "draft"
