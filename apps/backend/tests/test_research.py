import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import NotFoundError
from app.database.models import Base, Project
from app.schemas.project import ProjectCreate
from app.schemas.research import ResearchRecordCreate, ResearchRecordUpdate
from app.services.project import ProjectService
from app.services.research import ResearchService


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
    return p_service.create_project(ProjectCreate(name="Research Test Project"))


def test_research_crud_lifecycle(db_session, test_project):
    service = ResearchService(db_session)
    data = ResearchRecordCreate(
        title="Student user interview on job discovery",
        source_type="user_interview",
        source_name="Student Participant #104",
        author="Growth Team",
        observation_summary="Students seek shifts located within 15 minutes of campus.",
        interpretation_notes="Location proximity is the primary filtering factor.",
        evidence_data={"commute_minutes_max": 15},
    )
    created = service.create_record(data, project_id=test_project.id)

    assert created.id is not None
    assert created.project_id == test_project.id
    assert created.title == "Student user interview on job discovery"
    assert created.source_type == "user_interview"
    assert created.source_name == "Student Participant #104"
    assert created.observation_summary == "Students seek shifts located within 15 minutes of campus."
    assert created.collected_at is not None

    # Get by ID
    fetched = service.get_record(created.id, project_id=test_project.id)
    assert fetched.id == created.id

    # Update
    updated = service.update_record(
        created.id,
        ResearchRecordUpdate(title="Updated Title", observation_summary="Updated observation"),
        project_id=test_project.id,
    )
    assert updated.title == "Updated Title"
    assert updated.observation_summary == "Updated observation"

    # List
    items, total = service.list_records(project_id=test_project.id)
    assert total == 1
    assert len(items) == 1

    # Delete
    service.delete_record(created.id, project_id=test_project.id)
    with pytest.raises(NotFoundError):
        service.get_record(created.id, project_id=test_project.id)


def test_research_provenance_nullable_dates(db_session, test_project):
    service = ResearchService(db_session)
    data = ResearchRecordCreate(
        title="Manual observation without known dates",
        source_type="manual_observation",
        observation_summary="Noticed drop-off during onboarding.",
    )
    created = service.create_record(data, project_id=test_project.id)

    assert created.observed_at is None
    assert created.published_at is None
    assert created.collected_at is not None


def test_validation_user_interview_requires_source_name():
    with pytest.raises(ValueError, match="requires source_name"):
        ResearchRecordCreate(
            title="Interview without name",
            source_type="user_interview",
            observation_summary="Summary here",
        )


def test_validation_app_review_requires_quote_and_source_name():
    # Missing source_name
    with pytest.raises(ValueError, match="requires source_name"):
        ResearchRecordCreate(
            title="Review",
            source_type="app_review",
            source_quote="Great app",
            observation_summary="Summary",
        )
    # Missing quote
    with pytest.raises(ValueError, match="requires verbatim source_quote"):
        ResearchRecordCreate(
            title="Review",
            source_type="app_review",
            source_name="Play Store",
            observation_summary="Summary",
        )


def test_validation_competitor_analysis_requires_url_or_name():
    with pytest.raises(ValueError, match="requires at least one of source_url or source_name"):
        ResearchRecordCreate(
            title="Competitor",
            source_type="competitor_analysis",
            observation_summary="Summary",
        )
    # Valid with name
    valid = ResearchRecordCreate(
        title="Competitor",
        source_type="competitor_analysis",
        source_name="CompeteApp",
        observation_summary="Summary",
    )
    assert valid.source_name == "CompeteApp"


def test_validation_analytics_requires_evidence_data():
    # Missing evidence_data
    with pytest.raises(ValueError, match="requires non-empty evidence_data"):
        ResearchRecordCreate(
            title="Analytics",
            source_type="analytics",
            observation_summary="Summary",
        )
    # Empty dictionary
    with pytest.raises(ValueError, match="requires non-empty evidence_data"):
        ResearchRecordCreate(
            title="Analytics",
            source_type="analytics",
            evidence_data={},
            observation_summary="Summary",
        )
    # Metadata-only dictionary (no numeric metrics)
    with pytest.raises(ValueError, match="must contain at least one numeric metric"):
        ResearchRecordCreate(
            title="Analytics",
            source_type="analytics",
            evidence_data={"funnel_step": "checkout", "label": "dropoff"},
            observation_summary="Summary",
        )
    # Boolean-only dictionary (booleans rejected as numeric metrics)
    with pytest.raises(ValueError, match="must contain at least one numeric metric"):
        ResearchRecordCreate(
            title="Analytics",
            source_type="analytics",
            evidence_data={"is_converted": True, "has_error": False},
            observation_summary="Summary",
        )
    # Valid numeric-only
    valid_numeric = ResearchRecordCreate(
        title="Analytics Numeric Only",
        source_type="analytics",
        evidence_data={"churn_rate": 0.42},
        observation_summary="High churn rate observed",
    )
    assert valid_numeric.evidence_data["churn_rate"] == 0.42

    # Valid mixed numeric and metadata fields
    valid_mixed = ResearchRecordCreate(
        title="Analytics Mixed",
        source_type="analytics",
        evidence_data={"dau": 1250, "funnel_step": "payment_entry", "verified": True},
        observation_summary="Daily active users at payment step",
    )
    assert valid_mixed.evidence_data["dau"] == 1250
    assert valid_mixed.evidence_data["funnel_step"] == "payment_entry"


def test_validation_market_report_requires_attribution_and_evidence():
    # Missing source_name
    with pytest.raises(ValueError, match="requires source_name"):
        ResearchRecordCreate(
            title="Report Without Source Name",
            source_type="market_report",
            source_url="https://example.com/report",
            author="Jane Analyst",
            observation_summary="Summary",
        )
    # Has source_name, but neither source_url nor author
    with pytest.raises(ValueError, match="requires at least one of source_url or author"):
        ResearchRecordCreate(
            title="Report Without URL or Author",
            source_type="market_report",
            source_name="Gartner Research",
            observation_summary="Summary",
        )
    # Valid: source_name + source_url
    valid_url = ResearchRecordCreate(
        title="Report With URL",
        source_type="market_report",
        source_name="IDC",
        source_url="https://idc.com/reports/mobile-growth",
        observation_summary="Market share grew 15%",
    )
    assert valid_url.source_name == "IDC"
    assert valid_url.source_url == "https://idc.com/reports/mobile-growth"

    # Valid: source_name + author
    valid_author = ResearchRecordCreate(
        title="Report With Author",
        source_type="market_report",
        source_name="Forrester",
        author="John Doe",
        observation_summary="Enterprise SaaS expansion report",
    )
    assert valid_author.source_name == "Forrester"
    assert valid_author.author == "John Doe"


def test_validation_manual_observation():
    valid = ResearchRecordCreate(
        title="Observation",
        source_type="manual_observation",
        observation_summary="Factual note on flow",
    )
    assert valid.source_type == "manual_observation"
