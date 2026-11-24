import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import (
    Base,
    GoalMetricUpdate,
    GrowthOpportunity,
    GrowthStrategy,
    Project,
    StrategyGoal,
    StrategyOpportunityAssociation,
    StrategyStatusHistory,
)
from app.schemas.goal import StrategyGoalCreate
from app.schemas.opportunity import OpportunityCreate, OpportunityTransition
from app.schemas.project import ProjectCreate
from app.schemas.strategy import (
    GrowthStrategyCreate,
    GrowthStrategyTransition,
)
from app.schemas.strategy_association import StrategyOpportunityAssociateItem
from app.services.goal import GoalService
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
def p1(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Project 1"))


@pytest.fixture
def p2(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Project 2"))


class TestStrategyOpportunityAssociationRules:
    def test_draft_strategy_links_in_review_and_approved_opportunities(self, db_session, p1):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat = s_service.create_strategy(
            GrowthStrategyCreate(
                name="Q1 Activation",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )

        # Create opportunity in draft, move to in_review
        opp_review = o_service.create_opportunity(
            OpportunityCreate(
                title="Quick Apply Flow",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="activation",
            ),
            project_id=p1.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp_review.id,
            OpportunityTransition(status="in_review"),
            project_id=p1.id,
            actor="pm",
        )

        # Create opportunity, move to approved
        opp_approved = o_service.create_opportunity(
            OpportunityCreate(
                title="Instant Job Alerts",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="retention",
            ),
            project_id=p1.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp_approved.id,
            OpportunityTransition(status="in_review"),
            project_id=p1.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp_approved.id,
            OpportunityTransition(status="approved"),
            project_id=p1.id,
            actor="lead",
        )

        # Draft strategy successfully associates in_review and approved opportunities
        assocs = s_service.associate_opportunities(
            strat.id,
            [
                StrategyOpportunityAssociateItem(
                    opportunity_id=opp_review.id,
                    strategic_rationale="Core activation funnel step",
                ),
                StrategyOpportunityAssociateItem(
                    opportunity_id=opp_approved.id,
                    strategic_rationale="Retention reinforcement",
                ),
            ],
            project_id=p1.id,
        )
        assert len(assocs) == 2

        # Verify list associated opportunities
        listed = s_service.list_associated_opportunities(strat.id, project_id=p1.id)
        assert len(listed) == 2

    def test_draft_strategy_cannot_link_draft_opportunity(self, db_session, p1):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat = s_service.create_strategy(
            GrowthStrategyCreate(
                name="Strategy A",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )

        # Opportunity left in initial draft status
        opp_draft = o_service.create_opportunity(
            OpportunityCreate(
                title="Unreviewed Idea",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="acquisition",
            ),
            project_id=p1.id,
            actor="pm",
        )

        with pytest.raises(UnprocessableEntityError, match="in_review.*or.*approved"):
            s_service.associate_opportunities(
                strat.id,
                [StrategyOpportunityAssociateItem(opportunity_id=opp_draft.id)],
                project_id=p1.id,
            )

    def test_duplicate_association_updates_rationale(self, db_session, p1):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat = s_service.create_strategy(
            GrowthStrategyCreate(
                name="Duplicate Test",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )
        opp = o_service.create_opportunity(
            OpportunityCreate(
                title="Opportunity A",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="activation",
            ),
            project_id=p1.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp.id, OpportunityTransition(status="in_review"), project_id=p1.id, actor="pm"
        )

        # Initial link
        s_service.associate_opportunities(
            strat.id,
            [StrategyOpportunityAssociateItem(opportunity_id=opp.id, strategic_rationale="Initial")],
            project_id=p1.id,
        )

        # Re-link same opportunity with updated rationale
        assocs = s_service.associate_opportunities(
            strat.id,
            [StrategyOpportunityAssociateItem(opportunity_id=opp.id, strategic_rationale="Updated")],
            project_id=p1.id,
        )
        assert len(assocs) == 1
        assert assocs[0].strategic_rationale == "Updated"

        # Verify only 1 association exists in DB
        listed = s_service.list_associated_opportunities(strat.id, project_id=p1.id)
        assert len(listed) == 1
        assert listed[0][0].strategic_rationale == "Updated"

    def test_unlinking_opportunity(self, db_session, p1):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat = s_service.create_strategy(
            GrowthStrategyCreate(
                name="Unlink Test",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )
        opp = o_service.create_opportunity(
            OpportunityCreate(
                title="Opportunity To Unlink",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="activation",
            ),
            project_id=p1.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp.id, OpportunityTransition(status="in_review"), project_id=p1.id, actor="pm"
        )

        s_service.associate_opportunities(
            strat.id,
            [StrategyOpportunityAssociateItem(opportunity_id=opp.id)],
            project_id=p1.id,
        )

        # Unlink
        s_service.unlink_opportunity(strat.id, opportunity_id=opp.id, project_id=p1.id)
        listed = s_service.list_associated_opportunities(strat.id, project_id=p1.id)
        assert len(listed) == 0


class TestOpportunityRevalidationOnStrategyTransition:
    def test_transition_to_approved_requires_all_linked_opportunities_approved(self, db_session, p1):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat = s_service.create_strategy(
            GrowthStrategyCreate(
                name="Approval Gate Test",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )
        opp = o_service.create_opportunity(
            OpportunityCreate(
                title="Pending Review Opp",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="activation",
            ),
            project_id=p1.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp.id, OpportunityTransition(status="in_review"), project_id=p1.id, actor="pm"
        )

        # Link while draft
        s_service.associate_opportunities(
            strat.id,
            [StrategyOpportunityAssociateItem(opportunity_id=opp.id)],
            project_id=p1.id,
        )

        # Move strategy to in_review (allowed, since opp is in_review)
        s_service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="in_review"),
            project_id=p1.id,
            actor="lead",
        )

        # Attempt to approve strategy while opp is still in_review -> MUST BE REJECTED!
        with pytest.raises(UnprocessableEntityError, match="all linked opportunities to be approved"):
            s_service.transition_strategy(
                strat.id,
                GrowthStrategyTransition(status="approved"),
                project_id=p1.id,
                actor="vp",
            )

        # Approve the opportunity
        o_service.transition_opportunity(
            opp.id,
            OpportunityTransition(status="approved"),
            project_id=p1.id,
            actor="lead",
        )

        # Now strategy approval succeeds!
        approved_strat = s_service.transition_strategy(
            strat.id,
            GrowthStrategyTransition(status="approved"),
            project_id=p1.id,
            actor="vp",
        )
        assert approved_strat.status == "approved"


class TestMultiTenancyAndCompositeFKIsolation:
    def test_service_rejection_of_cross_project_opportunity_association(self, db_session, p1, p2):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat_p1 = s_service.create_strategy(
            GrowthStrategyCreate(
                name="P1 Strategy",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )

        opp_p2 = o_service.create_opportunity(
            OpportunityCreate(
                title="P2 Opportunity",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="activation",
            ),
            project_id=p2.id,
            actor="pm",
        )
        o_service.transition_opportunity(
            opp_p2.id, OpportunityTransition(status="in_review"), project_id=p2.id, actor="pm"
        )

        # Attempt to link P2 opportunity to P1 strategy under P1 scope
        with pytest.raises(NotFoundError, match="not found in this project"):
            s_service.associate_opportunities(
                strat_p1.id,
                [StrategyOpportunityAssociateItem(opportunity_id=opp_p2.id)],
                project_id=p1.id,
            )

    def test_database_composite_fk_rejection_for_association(self, db_session, p1, p2):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)

        strat_p1 = s_service.create_strategy(
            GrowthStrategyCreate(
                name="P1 Strategy",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )
        opp_p2 = o_service.create_opportunity(
            OpportunityCreate(
                title="P2 Opportunity",
                problem_statement="Problem",
                hypothesis="Hypothesis",
                proposed_mechanism="Mechanism",
                target_audience="Audience",
                category="activation",
            ),
            project_id=p2.id,
            actor="pm",
        )

        # Bypass service and insert directly into DB: (strategy_id=P1, opp_id=P2, project_id=P1)
        # Foreign key fk_assoc_strat_opportunity_project requires (opp_id, project_id) -> growth_opportunities
        # But opp_p2 has project_id=P2, so (opp_p2.id, p1.id) does NOT exist!
        assoc = StrategyOpportunityAssociation(
            strategy_id=strat_p1.id,
            opportunity_id=opp_p2.id,
            project_id=p1.id,
            strategic_rationale="Bypass attempt",
        )
        db_session.add(assoc)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_database_composite_fk_rejection_for_strategy_history(self, db_session, p1, p2):
        s_service = StrategyService(db_session)

        strat_p1 = s_service.create_strategy(
            GrowthStrategyCreate(
                name="P1 Strategy",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )

        # Attempt to insert bogus history referencing strat_p1 under project_id=P2
        bogus_history = StrategyStatusHistory(
            strategy_id=strat_p1.id,
            project_id=p2.id,
            previous_status="draft",
            new_status="in_review",
            reason="Illegal injection across tenant boundaries",
            actor="attacker",
        )
        db_session.add(bogus_history)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_database_composite_fk_rejection_for_goal_metric_update(self, db_session, p1, p2):
        s_service = StrategyService(db_session)
        g_service = GoalService(db_session)

        strat_p1 = s_service.create_strategy(
            GrowthStrategyCreate(
                name="P1 Strategy",
                strategic_vision="Vision",
                target_audience="Audience",
                time_horizon="Q1",
            ),
            project_id=p1.id,
            actor="lead",
        )
        goal_p1 = g_service.create_goal(
            strat_p1.id,
            StrategyGoalCreate(
                name="P1 Goal",
                metric_name="metric",
                metric_unit="unit",
                baseline_value=1.0,
                target_value=10.0,
            ),
            project_id=p1.id,
            actor="test",
        )

        # Attempt to insert metric update for goal_p1 under project_id=P2
        bogus_metric = GoalMetricUpdate(
            goal_id=goal_p1.id,
            project_id=p2.id,
            previous_value=1.0,
            new_value=5.0,
            notes="Cross tenant injection",
            actor="attacker",
        )
        db_session.add(bogus_metric)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
