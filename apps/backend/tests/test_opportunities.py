import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import Base
from app.schemas.opportunity import (
    PRIORITY_MATRIX,
    OpportunityCreate,
    OpportunityImpact,
    OpportunityEffort,
    OpportunityTransition,
    OpportunityUpdate,
    calculate_priority,
)
from app.schemas.project import ProjectCreate
from app.services.opportunity import OpportunityService
from app.services.project import ProjectService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_project(db_session):
    p_service = ProjectService(db_session)
    return p_service.create_project(ProjectCreate(name="Opportunity Test Project"))


def test_confidence_score_boundaries():
    # NULL is allowed
    opp_null = OpportunityCreate(
        title="Title",
        problem_statement="Problem",
        hypothesis="Hypothesis",
        proposed_mechanism="Mechanism",
        target_audience="Students",
        category="activation",
        confidence_score=None,
    )
    assert opp_null.confidence_score is None

    # 0.00 is allowed
    opp_zero = OpportunityCreate(
        title="Title",
        problem_statement="Problem",
        hypothesis="Hypothesis",
        proposed_mechanism="Mechanism",
        target_audience="Students",
        category="activation",
        confidence_score=0.00,
    )
    assert opp_zero.confidence_score == 0.00

    # 0.75 is allowed
    opp_mid = OpportunityCreate(
        title="Title",
        problem_statement="Problem",
        hypothesis="Hypothesis",
        proposed_mechanism="Mechanism",
        target_audience="Students",
        category="activation",
        confidence_score=0.75,
    )
    assert opp_mid.confidence_score == 0.75

    # 1.00 is allowed
    opp_one = OpportunityCreate(
        title="Title",
        problem_statement="Problem",
        hypothesis="Hypothesis",
        proposed_mechanism="Mechanism",
        target_audience="Students",
        category="activation",
        confidence_score=1.00,
    )
    assert opp_one.confidence_score == 1.00

    # Invalid below 0.00
    with pytest.raises(ValidationError):
        OpportunityCreate(
            title="Title",
            problem_statement="Problem",
            hypothesis="Hypothesis",
            proposed_mechanism="Mechanism",
            target_audience="Students",
            category="activation",
            confidence_score=-0.01,
        )

    # Invalid above 1.00
    with pytest.raises(ValidationError):
        OpportunityCreate(
            title="Title",
            problem_statement="Problem",
            hypothesis="Hypothesis",
            proposed_mechanism="Mechanism",
            target_audience="Students",
            category="activation",
            confidence_score=1.01,
        )


def test_priority_matrix_exhaustive():
    # All 12 valid combinations
    assert calculate_priority("critical", "low") == "p0_urgent"
    assert calculate_priority("critical", "medium") == "p0_urgent"
    assert calculate_priority("critical", "high") == "p1_high"
    assert calculate_priority("high", "low") == "p0_urgent"
    assert calculate_priority("high", "medium") == "p1_high"
    assert calculate_priority("high", "high") == "p2_medium"
    assert calculate_priority("medium", "low") == "p1_high"
    assert calculate_priority("medium", "medium") == "p2_medium"
    assert calculate_priority("medium", "high") == "p3_low"
    assert calculate_priority("low", "low") == "p2_medium"
    assert calculate_priority("low", "medium") == "p3_low"
    assert calculate_priority("low", "high") == "p3_low"

    assert len(PRIORITY_MATRIX) == 12

    # Unsupported combination raises ValueError
    with pytest.raises(ValueError, match="Exhaustive priority check failed"):
        calculate_priority("invalid_impact", "low")  # type: ignore


def test_opportunity_crud_and_slug_generation(db_session, test_project):
    service = OpportunityService(db_session)
    data = OpportunityCreate(
        title="One-Tap Apply For Students",
        problem_statement="Students take 5 minutes to submit applications.",
        hypothesis="If we provide one-tap apply, completion increases by 25%.",
        proposed_mechanism="Cache verified profile payloads on client.",
        target_audience="University students",
        category="activation",
        estimated_impact="critical",
        estimated_effort="low",
        confidence_score=0.85,
    )
    created = service.create_opportunity(data, project_id=test_project.id, actor="default")

    assert created.id is not None
    assert created.slug == "one-tap-apply-for-students"
    assert created.status == "draft"
    assert created.priority == "p0_urgent"
    assert float(created.confidence_score) == 0.85

    # Collision handling creates auto-suffix
    data2 = OpportunityCreate(
        title="One-Tap Apply For Students",
        problem_statement="Another problem statement.",
        hypothesis="Another hypothesis.",
        proposed_mechanism="Another mechanism.",
        target_audience="Another audience.",
        category="activation",
    )
    created2 = service.create_opportunity(data2, project_id=test_project.id, actor="default")
    assert created2.slug == "one-tap-apply-for-students-1"

    # Initial history created in the same transaction
    history = service.get_history(created.id, project_id=test_project.id)
    assert len(history) == 1
    assert history[0].previous_status is None
    assert history[0].new_status == "draft"
    assert history[0].actor == "default"


def test_lifecycle_transitions_and_mandatory_reasons(db_session, test_project):
    service = OpportunityService(db_session)
    opp = service.create_opportunity(
        OpportunityCreate(
            title="Lifecycle Test",
            problem_statement="P",
            hypothesis="H",
            proposed_mechanism="M",
            target_audience="A",
            category="activation",
        ),
        project_id=test_project.id,
        actor="default",
    )

    # 1. Invalid transition directly to approved
    with pytest.raises(ConflictError, match="Cannot transition"):
        service.transition_opportunity(
            opp.id,
            OpportunityTransition(status="approved"),
            project_id=test_project.id,
            actor="default",
        )

    # 2. Valid transition draft -> in_review
    opp = service.transition_opportunity(
        opp.id,
        OpportunityTransition(status="in_review"),
        project_id=test_project.id,
        actor="default",
    )
    assert opp.status == "in_review"

    # 3. Transition in_review -> rejected requires mandatory reason (>= 10 chars)
    with pytest.raises(UnprocessableEntityError, match="requires an explanatory reason"):
        service.transition_opportunity(
            opp.id,
            OpportunityTransition(status="rejected", reason=""),
            project_id=test_project.id,
            actor="default",
        )
    with pytest.raises(UnprocessableEntityError, match="at least 10 characters"):
        service.transition_opportunity(
            opp.id,
            OpportunityTransition(status="rejected", reason="Too short"),
            project_id=test_project.id,
            actor="default",
        )

    # Valid rejection with adequate reason
    opp = service.transition_opportunity(
        opp.id,
        OpportunityTransition(status="rejected", reason="Technical latency dependencies exceed Q4 goals"),
        project_id=test_project.id,
        actor="default",
    )
    assert opp.status == "rejected"

    # 4. Rejected -> draft requires reason
    with pytest.raises(UnprocessableEntityError, match="requires an explanatory reason"):
        service.transition_opportunity(
            opp.id,
            OpportunityTransition(status="draft"),
            project_id=test_project.id,
            actor="default",
        )

    opp = service.transition_opportunity(
        opp.id,
        OpportunityTransition(status="draft", reason="Re-evaluating with new user survey data"),
        project_id=test_project.id,
        actor="default",
    )
    assert opp.status == "draft"

    # Verify history audit trail
    history = service.get_history(opp.id, project_id=test_project.id)
    assert len(history) == 4
    statuses = [(h.previous_status, h.new_status) for h in history]
    assert statuses == [
        (None, "draft"),
        ("draft", "in_review"),
        ("in_review", "rejected"),
        ("rejected", "draft"),
    ]


def test_deletion_rejected_when_audit_records_exist(db_session, test_project):
    service = OpportunityService(db_session)
    opp = service.create_opportunity(
        OpportunityCreate(
            title="Delete Guard Test",
            problem_statement="P",
            hypothesis="H",
            proposed_mechanism="M",
            target_audience="A",
            category="activation",
        ),
        project_id=test_project.id,
        actor="default",
    )

    # Destructive deletion is blocked to preserve audit trail
    with pytest.raises(ConflictError, match="Opportunities with audit history cannot be deleted"):
        service.delete_opportunity(opp.id, project_id=test_project.id)

    # Proper action is archival
    opp = service.transition_opportunity(
        opp.id,
        OpportunityTransition(status="archived", reason="Archived instead of deleted"),
        project_id=test_project.id,
        actor="default",
    )
    assert opp.status == "archived"
