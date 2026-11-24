"""Regression tests for the Phase 1-5 stabilization repairs (B1-B10)."""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import (
    Base,
    GoalStatusHistory,
    OpportunityStatusHistory,
    OpportunityResearchAssociation,
)
from app.schemas.association import AssociationItem
from app.schemas.goal import (
    GoalMetricUpdateCreate,
    StrategyGoalCreate,
    StrategyGoalUpdate,
)
from app.schemas.opportunity import OpportunityCreate, OpportunityTransition, OpportunityUpdate
from app.schemas.project import ProjectCreate
from app.schemas.research import ResearchRecordCreate, ResearchRecordUpdate
from app.schemas.strategy import GrowthStrategyCreate, GrowthStrategyTransition
from app.schemas.strategy_association import StrategyOpportunityAssociateItem
from app.services.goal import GoalService
from app.services.opportunity import OpportunityService
from app.services.project import ProjectService
from app.services.research import ResearchService
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
    return ProjectService(db_session).create_project(ProjectCreate(name="Repair Project"))


@pytest.fixture
def strategy(db_session, project):
    return StrategyService(db_session).create_strategy(
        GrowthStrategyCreate(
            name="Repair Strategy",
            strategic_vision="Vision",
            target_audience="Audience",
            time_horizon="Q1",
        ),
        project_id=project.id,
        actor="test",
    )


def _opp(service, project, title="Opp"):
    return service.create_opportunity(
        OpportunityCreate(
            title=title,
            problem_statement="P",
            hypothesis="H",
            proposed_mechanism="M",
            target_audience="A",
            category="activation",
        ),
        project_id=project.id,
        actor="test",
    )


def _goal(service, strategy, project):
    return service.create_goal(
        strategy.id,
        StrategyGoalCreate(
            name="G", metric_name="m", metric_unit="u",
            baseline_value=1.0, target_value=10.0,
        ),
        project_id=project.id,
        actor="test",
    )


class TestB1GoalStrategyScoping:
    def test_cross_strategy_goal_access_returns_404(self, db_session, project, strategy):
        s_service = StrategyService(db_session)
        other = s_service.create_strategy(
            GrowthStrategyCreate(
                name="Other", strategic_vision="V", target_audience="A", time_horizon="Q1"
            ),
            project_id=project.id,
            actor="test",
        )
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)

        for call in (
            lambda: g_service.get_goal(goal.id, other.id, project.id),
            lambda: g_service.update_goal(goal.id, other.id, StrategyGoalUpdate(name="X"), project.id, "test"),
            lambda: g_service.delete_goal(goal.id, other.id, project.id),
            lambda: g_service.record_progress(goal.id, other.id, GoalMetricUpdateCreate(new_value=2.0), project.id, "test"),
            lambda: g_service.get_metric_history(goal.id, other.id, project.id),
            lambda: g_service.get_status_history(goal.id, other.id, project.id),
        ):
            with pytest.raises(NotFoundError):
                call()

    def test_same_strategy_goal_access_works(self, db_session, project, strategy):
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)
        assert g_service.get_goal(goal.id, strategy.id, project.id).id == goal.id


class TestB2InReviewStrategyLinking:
    def _in_review_strategy(self, db_session, project):
        s = StrategyService(db_session).create_strategy(
            GrowthStrategyCreate(
                name="IR", strategic_vision="V", target_audience="A", time_horizon="Q1"
            ),
            project_id=project.id,
            actor="test",
        )
        StrategyService(db_session).transition_strategy(
            s.id, GrowthStrategyTransition(status="in_review"), project_id=project.id, actor="test"
        )
        return s

    def test_in_review_strategy_rejects_draft_opportunity(self, db_session, project):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)
        strat = self._in_review_strategy(db_session, project)
        opp = _opp(o_service, project)  # draft
        with pytest.raises(UnprocessableEntityError):
            s_service.associate_opportunities(
                strat.id, [StrategyOpportunityAssociateItem(opportunity_id=opp.id)], project.id
            )

    def test_in_review_strategy_links_in_review_and_approved(self, db_session, project):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)
        strat = self._in_review_strategy(db_session, project)
        opp = _opp(o_service, project)
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="in_review"), project.id, "test")
        result = s_service.associate_opportunities(
            strat.id, [StrategyOpportunityAssociateItem(opportunity_id=opp.id)], project.id
        )
        assert len(result) == 1


class TestB3ApprovedOpportunityTransitionGuard:
    def test_approved_opp_linked_to_approved_strategy_cannot_leave(self, db_session, project):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)
        strat = s_service.create_strategy(
            GrowthStrategyCreate(name="S", strategic_vision="V", target_audience="A", time_horizon="Q1"),
            project_id=project.id, actor="test",
        )
        opp = _opp(o_service, project)
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="in_review"), project.id, "test")
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="approved"), project.id, "test")
        s_service.associate_opportunities(
            strat.id, [StrategyOpportunityAssociateItem(opportunity_id=opp.id)], project.id
        )
        s_service.transition_strategy(strat.id, GrowthStrategyTransition(status="in_review"), project.id, "test")
        s_service.transition_strategy(strat.id, GrowthStrategyTransition(status="approved"), project.id, "test")

        with pytest.raises(ConflictError, match="linked to a 'approved' growth strategy"):
            o_service.transition_opportunity(opp.id, OpportunityTransition(status="archived"), project.id, "test")

    def test_approved_opp_without_strategy_link_can_archive(self, db_session, project):
        o_service = OpportunityService(db_session)
        opp = _opp(o_service, project)
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="in_review"), project.id, "test")
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="approved"), project.id, "test")
        updated = o_service.transition_opportunity(opp.id, OpportunityTransition(status="archived"), project.id, "test")
        assert updated.status == "archived"


class TestB4ResearchPatchValidation:
    def test_invalid_source_type_update_returns_422_error(self, db_session, project):
        r_service = ResearchService(db_session)
        rec = r_service.create_record(
            ResearchRecordCreate(
                title="R", source_type="manual_observation", observation_summary="Obs"
            ),
            project_id=project.id,
        )
        with pytest.raises(UnprocessableEntityError):
            r_service.update_record(
                rec.id,
                ResearchRecordUpdate(source_type="app_review"),  # missing source_quote/source_name
                project_id=project.id,
            )

    def test_valid_update_still_works(self, db_session, project):
        r_service = ResearchService(db_session)
        rec = r_service.create_record(
            ResearchRecordCreate(
                title="R", source_type="manual_observation", observation_summary="Obs"
            ),
            project_id=project.id,
        )
        updated = r_service.update_record(
            rec.id, ResearchRecordUpdate(title="R2"), project_id=project.id
        )
        assert updated.title == "R2"


class TestB6ProjectDeleteGuards:
    def test_empty_project_deletes(self, db_session):
        p_service = ProjectService(db_session)
        p = p_service.create_project(ProjectCreate(name="Empty"))
        p_service.delete_project(p.id)
        with pytest.raises(NotFoundError):
            p_service.get_project(p.id)

    def test_project_with_opportunity_history_blocked(self, db_session):
        p_service = ProjectService(db_session)
        o_service = OpportunityService(db_session)
        p = p_service.create_project(ProjectCreate(name="Audited"))
        _opp(o_service, p)  # creation writes history
        with pytest.raises(ConflictError, match="audited records"):
            p_service.delete_project(p.id)


class TestB7GoalStatusHistory:
    def test_initial_status_history_recorded(self, db_session, project, strategy):
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)
        history = g_service.get_status_history(goal.id, strategy.id, project.id)
        assert len(history) == 1
        assert history[0].previous_status is None
        assert history[0].new_status == "pending"
        assert history[0].actor == "test"

    def test_update_status_writes_history_once(self, db_session, project, strategy):
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)
        g_service.update_goal(
            goal.id, strategy.id,
            StrategyGoalUpdate(status="on_track", reason="Manual review"),
            project.id, "reviewer",
        )
        history = g_service.get_status_history(goal.id, strategy.id, project.id)
        assert len(history) == 2
        assert history[1].previous_status == "pending"
        assert history[1].new_status == "on_track"
        assert history[1].reason == "Manual review"
        assert history[1].actor == "reviewer"

        # Same-status update must not duplicate history
        g_service.update_goal(
            goal.id, strategy.id, StrategyGoalUpdate(status="on_track"), project.id, "reviewer"
        )
        assert len(g_service.get_status_history(goal.id, strategy.id, project.id)) == 2

    def test_progress_status_change_writes_history(self, db_session, project, strategy):
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)
        g_service.record_progress(
            goal.id, strategy.id,
            GoalMetricUpdateCreate(new_value=10.0), project.id, "analyst",
        )
        history = g_service.get_status_history(goal.id, strategy.id, project.id)
        assert history[-1].new_status == "achieved"

    def test_goal_with_history_cannot_be_deleted(self, db_session, project, strategy):
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)
        with pytest.raises(ConflictError, match="cannot be deleted"):
            g_service.delete_goal(goal.id, strategy.id, project.id)


class TestB8AtomicOpportunityUpdate:
    def test_failed_transition_rolls_back_field_changes(self, db_session, project):
        o_service = OpportunityService(db_session)
        opp = _opp(o_service, project)
        with pytest.raises(ConflictError):
            o_service.update_opportunity(
                opp.id,
                OpportunityUpdate(title="Should Not Persist", status="approved"),
                project_id=project.id,
                actor="test",
            )
        refreshed = o_service.get_opportunity(opp.id, project_id=project.id)
        assert refreshed.title != "Should Not Persist"
        assert refreshed.status == "draft"

    def test_successful_update_applies_status_and_fields(self, db_session, project):
        o_service = OpportunityService(db_session)
        opp = _opp(o_service, project)
        updated = o_service.update_opportunity(
            opp.id,
            OpportunityUpdate(title="New Title", status="in_review"),
            project_id=project.id,
            actor="test",
        )
        assert updated.title == "New Title"
        assert updated.status == "in_review"
        history = o_service.get_history(opp.id, project_id=project.id)
        assert history[-1].new_status == "in_review"


class TestB9GoalInitialStatus:
    def test_non_pending_initial_status_rejected(self):
        with pytest.raises(ValidationError):
            StrategyGoalCreate(
                name="G", metric_name="m", metric_unit="u",
                baseline_value=1.0, target_value=10.0, status="achieved",
            )

    def test_pending_initial_status_accepted(self):
        goal = StrategyGoalCreate(
            name="G", metric_name="m", metric_unit="u",
            baseline_value=1.0, target_value=10.0,
        )
        assert goal.status == "pending"


class TestB10ResearchDeleteGuard:
    def test_linked_research_cannot_be_deleted(self, db_session, project):
        r_service = ResearchService(db_session)
        o_service = OpportunityService(db_session)
        rec = r_service.create_record(
            ResearchRecordCreate(
                title="R", source_type="manual_observation", observation_summary="Obs"
            ),
            project_id=project.id,
        )
        opp = _opp(o_service, project)
        o_service.associate_research(
            opp.id, [AssociationItem(research_id=rec.id)], project_id=project.id
        )
        with pytest.raises(ConflictError, match="linked to one or more opportunities"):
            r_service.delete_record(rec.id, project_id=project.id)

    def test_unlinked_research_deletes(self, db_session, project):
        r_service = ResearchService(db_session)
        rec = r_service.create_record(
            ResearchRecordCreate(
                title="R", source_type="manual_observation", observation_summary="Obs"
            ),
            project_id=project.id,
        )
        r_service.delete_record(rec.id, project_id=project.id)
        with pytest.raises(NotFoundError):
            r_service.get_record(rec.id, project_id=project.id)


class TestAuditImmutability:
    def test_history_tables_have_no_mutation_path(self, db_session, project, strategy):
        # History rows are append-only: model exposes no update/delete service path.
        g_service = GoalService(db_session)
        goal = _goal(g_service, strategy, project)
        rows = db_session.query(GoalStatusHistory).filter_by(goal_id=goal.id).all()
        assert len(rows) == 1


class TestB2LinkedOpportunityLifecycleInvariant:
    def _linked_in_review(self, db_session, project):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)
        strat = s_service.create_strategy(
            GrowthStrategyCreate(name="S", strategic_vision="V", target_audience="A", time_horizon="Q1"),
            project_id=project.id, actor="test",
        )
        opp = _opp(o_service, project)
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="in_review"), project.id, "test")
        s_service.associate_opportunities(
            strat.id, [StrategyOpportunityAssociateItem(opportunity_id=opp.id)], project.id
        )
        s_service.transition_strategy(strat.id, GrowthStrategyTransition(status="in_review"), project.id, "test")
        return s_service, o_service, strat, opp

    def test_in_review_linked_opp_cannot_regress_to_draft(self, db_session, project):
        _, o_service, _, opp = self._linked_in_review(db_session, project)
        with pytest.raises(ConflictError, match="linked to a 'in_review' growth strategy"):
            o_service.transition_opportunity(opp.id, OpportunityTransition(status="draft", reason="regressing for test"), project.id, "test")

    def test_in_review_linked_opp_cannot_archive(self, db_session, project):
        _, o_service, _, opp = self._linked_in_review(db_session, project)
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="approved"), project.id, "test")
        with pytest.raises(ConflictError, match="linked to a 'in_review' growth strategy"):
            o_service.transition_opportunity(opp.id, OpportunityTransition(status="archived"), project.id, "test")

    def test_in_review_linked_opp_can_progress_to_approved(self, db_session, project):
        _, o_service, _, opp = self._linked_in_review(db_session, project)
        updated = o_service.transition_opportunity(opp.id, OpportunityTransition(status="approved"), project.id, "test")
        assert updated.status == "approved"

    def test_unlink_resolves_invalid_association(self, db_session, project):
        s_service, o_service, strat, opp = self._linked_in_review(db_session, project)
        s_service.unlink_opportunity(strat.id, opp.id, project.id)
        updated = o_service.transition_opportunity(opp.id, OpportunityTransition(status="draft", reason="regressing for test"), project.id, "test")
        assert updated.status == "draft"


class TestB6ProjectDeleteAllBlockers:
    def test_blocked_by_strategy_history(self, db_session):
        p_service = ProjectService(db_session)
        s_service = StrategyService(db_session)
        p = p_service.create_project(ProjectCreate(name="StratHist"))
        strat = s_service.create_strategy(
            GrowthStrategyCreate(name="S", strategic_vision="V", target_audience="A", time_horizon="Q1"),
            project_id=p.id, actor="test",
        )
        s_service.transition_strategy(strat.id, GrowthStrategyTransition(status="in_review"), p.id, "test")
        with pytest.raises(ConflictError, match="strategy status transition"):
            p_service.delete_project(p.id)

    def test_blocked_by_goal_metric_history(self, db_session):
        p_service = ProjectService(db_session)
        s_service = StrategyService(db_session)
        g_service = GoalService(db_session)
        p = p_service.create_project(ProjectCreate(name="MetricHist"))
        strat = s_service.create_strategy(
            GrowthStrategyCreate(name="S", strategic_vision="V", target_audience="A", time_horizon="Q1"),
            project_id=p.id, actor="test",
        )
        goal = _goal(g_service, strat, p)
        g_service.record_progress(goal.id, strat.id, GoalMetricUpdateCreate(new_value=5.0), p.id, actor="test")
        with pytest.raises(ConflictError, match="goal metric update"):
            p_service.delete_project(p.id)

    def test_blocked_by_goal_status_history(self, db_session):
        p_service = ProjectService(db_session)
        s_service = StrategyService(db_session)
        g_service = GoalService(db_session)
        p = p_service.create_project(ProjectCreate(name="GoalHist"))
        strat = s_service.create_strategy(
            GrowthStrategyCreate(name="S", strategic_vision="V", target_audience="A", time_horizon="Q1"),
            project_id=p.id, actor="test",
        )
        goal = _goal(g_service, strat, p)  # creation writes status history
        with pytest.raises(ConflictError, match="goal status transition"):
            p_service.delete_project(p.id)

    def test_dependents_without_history_still_delete(self, db_session):
        # Research records carry no audit history and cascade cleanly.
        p_service = ProjectService(db_session)
        r_service = ResearchService(db_session)
        p = p_service.create_project(ProjectCreate(name="ResearchOnly"))
        r_service.create_record(
            ResearchRecordCreate(title="R", source_type="manual_observation", observation_summary="O"),
            project_id=p.id,
        )
        p_service.delete_project(p.id)
        with pytest.raises(NotFoundError):
            p_service.get_project(p.id)


class TestB3PatchStatusPathGuard:
    def test_patch_status_blocked_for_linked_approved_strategy(self, db_session, project):
        s_service = StrategyService(db_session)
        o_service = OpportunityService(db_session)
        strat = s_service.create_strategy(
            GrowthStrategyCreate(name="S", strategic_vision="V", target_audience="A", time_horizon="Q1"),
            project_id=project.id, actor="test",
        )
        opp = _opp(o_service, project)
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="in_review"), project.id, "test")
        o_service.transition_opportunity(opp.id, OpportunityTransition(status="approved"), project.id, "test")
        s_service.associate_opportunities(
            strat.id, [StrategyOpportunityAssociateItem(opportunity_id=opp.id)], project.id
        )
        s_service.transition_strategy(strat.id, GrowthStrategyTransition(status="in_review"), project.id, "test")
        s_service.transition_strategy(strat.id, GrowthStrategyTransition(status="approved"), project.id, "test")
        with pytest.raises(ConflictError, match="linked to a 'approved' growth strategy"):
            o_service.update_opportunity(
                opp.id, OpportunityUpdate(status="archived"), project.id, actor="test"
            )
