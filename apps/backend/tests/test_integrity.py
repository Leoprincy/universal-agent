import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import NotFoundError
from app.database.models import (
    Base,
    OpportunityResearchAssociation,
    OpportunityStatusHistory,
)
from app.schemas.association import AssociationItem
from app.schemas.opportunity import OpportunityCreate
from app.schemas.project import ProjectCreate
from app.schemas.research import ResearchRecordCreate
from app.services.opportunity import OpportunityService
from app.services.project import ProjectService
from app.services.research import ResearchService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Enable SQLite foreign key enforcement
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


def test_cross_project_association_service_rejection(db_session):
    p_service = ProjectService(db_session)
    r_service = ResearchService(db_session)
    o_service = OpportunityService(db_session)

    # Create Project 1 and Project 2
    p1 = p_service.create_project(ProjectCreate(name="Project 1"))
    p2 = p_service.create_project(ProjectCreate(name="Project 2"))

    # Research record in Project 1
    rec1 = r_service.create_record(
        ResearchRecordCreate(
            title="P1 Evidence",
            source_type="manual_observation",
            observation_summary="Observation for P1",
        ),
        project_id=p1.id,
    )

    # Opportunity in Project 2
    opp2 = o_service.create_opportunity(
        OpportunityCreate(
            title="P2 Opportunity",
            problem_statement="Problem 2",
            hypothesis="Hypothesis 2",
            proposed_mechanism="Mechanism 2",
            target_audience="Audience 2",
            category="activation",
        ),
        project_id=p2.id,
        actor="default",
    )

    # Attempting to link P1 research into P2 opportunity via service must be rejected
    with pytest.raises(NotFoundError, match="not found in this project"):
        o_service.associate_research(
            opp2.id,
            [AssociationItem(research_id=rec1.id, notes="Cross project link attempt")],
            project_id=p2.id,
        )


def test_cross_project_database_foreign_key_integrity(db_session):
    p_service = ProjectService(db_session)
    r_service = ResearchService(db_session)
    o_service = OpportunityService(db_session)

    p1 = p_service.create_project(ProjectCreate(name="Integrity Proj 1"))
    p2 = p_service.create_project(ProjectCreate(name="Integrity Proj 2"))

    rec1 = r_service.create_record(
        ResearchRecordCreate(
            title="P1 Evidence",
            source_type="manual_observation",
            observation_summary="Observation for P1",
        ),
        project_id=p1.id,
    )

    opp2 = o_service.create_opportunity(
        OpportunityCreate(
            title="P2 Opportunity",
            problem_statement="Problem 2",
            hypothesis="Hypothesis 2",
            proposed_mechanism="Mechanism 2",
            target_audience="Audience 2",
            category="activation",
        ),
        project_id=p2.id,
        actor="default",
    )

    # Attempt direct DB insert linking Opp(P2) with Rec(P1) under project_id P2
    # Rec(P1) has (id=rec1.id, project_id=p1.id).
    # Association constraint requires (research_id, project_id) -> research_records(id, project_id).
    # Since assoc has project_id=p2.id, (rec1.id, p2.id) does not exist in research_records!
    assoc = OpportunityResearchAssociation(
        opportunity_id=opp2.id,
        research_id=rec1.id,
        project_id=p2.id,
        notes="Bypass attempt",
    )
    db_session.add(assoc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cross_project_history_foreign_key_integrity(db_session):
    p_service = ProjectService(db_session)
    o_service = OpportunityService(db_session)

    p1 = p_service.create_project(ProjectCreate(name="History Proj 1"))
    p2 = p_service.create_project(ProjectCreate(name="History Proj 2"))

    opp1 = o_service.create_opportunity(
        OpportunityCreate(
            title="P1 Opportunity",
            problem_statement="Problem 1",
            hypothesis="Hypothesis 1",
            proposed_mechanism="Mechanism 1",
            target_audience="Audience 1",
            category="activation",
        ),
        project_id=p1.id,
        actor="default",
    )

    # Attempt to insert status history row for opp1 but with project_id=p2.id
    # FK requires (opportunity_id, project_id) -> growth_opportunities(id, project_id).
    # (opp1.id, p2.id) does not exist in growth_opportunities!
    bogus_history = OpportunityStatusHistory(
        opportunity_id=opp1.id,
        project_id=p2.id,
        previous_status="draft",
        new_status="in_review",
        reason="Invalid tenant history injection",
        actor="hacker",
    )
    db_session.add(bogus_history)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_workspace_isolation_on_research_and_opportunities(db_session):
    p_service = ProjectService(db_session)
    r_service = ResearchService(db_session)
    o_service = OpportunityService(db_session)

    p_a = p_service.create_project(ProjectCreate(name="Team A Proj"), owner="team-a")
    p_b = p_service.create_project(ProjectCreate(name="Team B Proj"), owner="team-b")

    rec_a = r_service.create_record(
        ResearchRecordCreate(
            title="Team A Secret Evidence",
            source_type="manual_observation",
            observation_summary="Observation A",
        ),
        project_id=p_a.id,
    )

    # Team B user cannot find Project A
    with pytest.raises(NotFoundError):
        p_service.get_project(p_a.id, owner="team-b")
