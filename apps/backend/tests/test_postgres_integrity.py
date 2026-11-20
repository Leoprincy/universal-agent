"""
PostgreSQL integration tests for Phase 4 cross-project composite foreign key
enforcement and constraints.

These tests run exclusively against a dedicated test database specified via
UGA_TEST_DATABASE_URL. They never fall back to the application database
(UGA_DATABASE_URL or settings.database_url).

If UGA_TEST_DATABASE_URL is not configured, these tests are skipped.
Unit-level constraint and composite FK verification is covered unconditionally
by tests/test_integrity.py (SQLite with PRAGMA foreign_keys = ON).
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import (
    GrowthOpportunity,
    OpportunityResearchAssociation,
    OpportunityStatusHistory,
    Project,
    ResearchRecord,
)

# ---------------------------------------------------------------------------
# Strict test database URL resolution:
# Reads ONLY UGA_TEST_DATABASE_URL. Never falls back to UGA_DATABASE_URL
# or settings.database_url.
# ---------------------------------------------------------------------------


def _get_pg_test_url() -> str | None:
    """Return the dedicated test PostgreSQL URL from UGA_TEST_DATABASE_URL only.

    Strictly never falls back to UGA_DATABASE_URL or application settings.
    Returns None if UGA_TEST_DATABASE_URL is not set or does not use PostgreSQL.
    """
    raw = os.getenv("UGA_TEST_DATABASE_URL", "").strip()
    if not raw:
        return None
    if not raw.startswith("postgresql"):
        return None
    return raw


PG_TEST_URL = _get_pg_test_url()

pytestmark = pytest.mark.skipif(
    PG_TEST_URL is None,
    reason="UGA_TEST_DATABASE_URL is not configured (dedicated test database required)",
)


# ---------------------------------------------------------------------------
# Fixtures: External-transaction pattern with nested savepoint isolation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_engine():
    """Create a PostgreSQL engine for the test module."""
    engine = create_engine(PG_TEST_URL, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """Provide a PostgreSQL session using SQLAlchemy's external-transaction pattern.

    Binds the session to an open connection with an enclosing transaction.
    With join_transaction_mode="create_savepoint", all session-level operations
    (including flushes, rollbacks, and commits) operate within a nested savepoint
    and cannot persist changes outside the enclosing transaction.
    The outer transaction is always rolled back in the finally block.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def _make_project(session: Session, suffix: str) -> Project:
    """Insert an isolated test project."""
    p = Project(
        id=str(uuid.uuid4()),
        name=f"PG Test Project {suffix}",
        slug=f"pg-test-project-{suffix}-{uuid.uuid4().hex[:8]}",
        owner="pg-test-owner",
    )
    session.add(p)
    session.flush()
    return p


def _make_research(session: Session, project: Project, suffix: str) -> ResearchRecord:
    """Insert an isolated test research record."""
    r = ResearchRecord(
        id=str(uuid.uuid4()),
        project_id=project.id,
        title=f"PG Test Research {suffix}",
        source_type="manual_observation",
        observation_summary=f"Test observation {suffix}",
    )
    session.add(r)
    session.flush()
    return r


def _make_opportunity(
    session: Session, project: Project, suffix: str
) -> GrowthOpportunity:
    """Insert an isolated test opportunity."""
    opp = GrowthOpportunity(
        id=str(uuid.uuid4()),
        project_id=project.id,
        title=f"PG Test Opportunity {suffix}",
        slug=f"pg-test-opp-{suffix}-{uuid.uuid4().hex[:8]}",
        problem_statement="Problem",
        hypothesis="Hypothesis",
        proposed_mechanism="Mechanism",
        target_audience="Audience",
        category="activation",
        status="draft",
        estimated_impact="medium",
        estimated_effort="medium",
        priority="p2_medium",
    )
    session.add(opp)
    session.flush()
    return opp


# ---------------------------------------------------------------------------
# Tests: Composite FK, Delete Restriction, and CHECK Constraints
# ---------------------------------------------------------------------------


class TestPostgresCrossProjectAssociation:
    """Verify that PostgreSQL composite FK on opportunity_research_associations
    prevents linking research from one project to an opportunity in another."""

    def test_valid_same_project_association_succeeds(self, pg_session):
        """Positive case: association within the same project is allowed."""
        p = _make_project(pg_session, "same-proj")
        r = _make_research(pg_session, p, "same-proj")
        opp = _make_opportunity(pg_session, p, "same-proj")

        assoc = OpportunityResearchAssociation(
            opportunity_id=opp.id,
            research_id=r.id,
            project_id=p.id,
            notes="Valid same-project link",
        )
        pg_session.add(assoc)
        pg_session.flush()
        assert assoc.project_id == p.id

    def test_cross_project_association_rejected_by_research_fk(self, pg_session):
        """Association with research from a different project is rejected
        by fk_assoc_research_project."""
        p1 = _make_project(pg_session, "assoc-p1")
        p2 = _make_project(pg_session, "assoc-p2")

        r1 = _make_research(pg_session, p1, "assoc-r1")
        opp2 = _make_opportunity(pg_session, p2, "assoc-opp2")

        assoc = OpportunityResearchAssociation(
            opportunity_id=opp2.id,
            research_id=r1.id,
            project_id=p2.id,
            notes="Cross-project bypass attempt",
        )
        pg_session.add(assoc)
        with pytest.raises(IntegrityError, match="fk_assoc_research_project"):
            pg_session.flush()
        pg_session.rollback()

    def test_cross_project_association_rejected_by_opportunity_fk(self, pg_session):
        """Association referencing wrong project for the opportunity is rejected
        by fk_assoc_opportunity_project."""
        p1 = _make_project(pg_session, "assoc-opp-p1")
        p2 = _make_project(pg_session, "assoc-opp-p2")

        r2 = _make_research(pg_session, p2, "assoc-opp-r2")
        opp1 = _make_opportunity(pg_session, p1, "assoc-opp-opp1")

        assoc = OpportunityResearchAssociation(
            opportunity_id=opp1.id,
            research_id=r2.id,
            project_id=p2.id,
            notes="Cross-project opp bypass attempt",
        )
        pg_session.add(assoc)
        with pytest.raises(IntegrityError, match="fk_assoc_opportunity_project"):
            pg_session.flush()
        pg_session.rollback()


class TestPostgresCrossProjectHistory:
    """Verify that PostgreSQL composite FK on opportunity_status_history
    prevents inserting history for an opportunity under a different project."""

    def test_valid_same_project_history_succeeds(self, pg_session):
        """Positive case: history within the same project is allowed."""
        p = _make_project(pg_session, "hist-same")
        opp = _make_opportunity(pg_session, p, "hist-same")

        h = OpportunityStatusHistory(
            id=str(uuid.uuid4()),
            opportunity_id=opp.id,
            project_id=p.id,
            previous_status=None,
            new_status="draft",
            reason="Initial creation",
            actor="pg-test-owner",
        )
        pg_session.add(h)
        pg_session.flush()
        assert h.project_id == p.id

    def test_cross_project_history_rejected(self, pg_session):
        """History referencing an opportunity under a different project
        is rejected by fk_history_opportunity_project."""
        p1 = _make_project(pg_session, "hist-p1")
        p2 = _make_project(pg_session, "hist-p2")

        opp1 = _make_opportunity(pg_session, p1, "hist-opp1")

        bogus = OpportunityStatusHistory(
            id=str(uuid.uuid4()),
            opportunity_id=opp1.id,
            project_id=p2.id,
            previous_status="draft",
            new_status="in_review",
            reason="Cross-project history injection",
            actor="attacker",
        )
        pg_session.add(bogus)
        with pytest.raises(IntegrityError, match="fk_history_opportunity_project"):
            pg_session.flush()
        pg_session.rollback()


class TestPostgresDeleteRestriction:
    """Verify that ON DELETE RESTRICT on status history prevents opportunity
    deletion when history records exist."""

    def test_opportunity_with_history_cannot_be_deleted(self, pg_session):
        """Deleting an opportunity that has status history is blocked
        at the database level by ON DELETE RESTRICT."""
        p = _make_project(pg_session, "del-restrict")
        opp = _make_opportunity(pg_session, p, "del-restrict")

        h = OpportunityStatusHistory(
            id=str(uuid.uuid4()),
            opportunity_id=opp.id,
            project_id=p.id,
            previous_status=None,
            new_status="draft",
            reason="Creation record",
            actor="pg-test-owner",
        )
        pg_session.add(h)
        pg_session.flush()

        pg_session.delete(opp)
        with pytest.raises(IntegrityError, match="fk_history_opportunity_project"):
            pg_session.flush()
        pg_session.rollback()


class TestPostgresConfidenceScoreConstraint:
    """Verify that the CHECK constraint on confidence_score is enforced
    at the PostgreSQL level."""

    def test_valid_confidence_null(self, pg_session):
        p = _make_project(pg_session, "conf-null")
        opp = _make_opportunity(pg_session, p, "conf-null")
        opp.confidence_score = None
        pg_session.flush()

    def test_valid_confidence_zero(self, pg_session):
        p = _make_project(pg_session, "conf-zero")
        opp = _make_opportunity(pg_session, p, "conf-zero")
        opp.confidence_score = 0.00
        pg_session.flush()

    def test_valid_confidence_one(self, pg_session):
        p = _make_project(pg_session, "conf-one")
        opp = _make_opportunity(pg_session, p, "conf-one")
        opp.confidence_score = 1.00
        pg_session.flush()

    def test_invalid_confidence_above_one(self, pg_session):
        p = _make_project(pg_session, "conf-high")
        opp = _make_opportunity(pg_session, p, "conf-high")
        opp.confidence_score = 1.50
        with pytest.raises(IntegrityError, match="ck_growth_opportunities_confidence"):
            pg_session.flush()
        pg_session.rollback()

    def test_invalid_confidence_below_zero(self, pg_session):
        p = _make_project(pg_session, "conf-low")
        opp = _make_opportunity(pg_session, p, "conf-low")
        opp.confidence_score = -0.10
        with pytest.raises(IntegrityError, match="ck_growth_opportunities_confidence"):
            pg_session.flush()
        pg_session.rollback()
