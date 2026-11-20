import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    owner: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="default",
        server_default="default",
        index=True,
    )
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


class ResearchRecord(Base):
    __tablename__ = "research_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_research_records_id_project"),
        CheckConstraint(
            "source_type IN ('user_interview', 'app_review', 'competitor_analysis', 'analytics', 'market_report', 'manual_observation')",
            name="ck_research_records_source_type",
        ),
        Index("ix_research_records_project_source_type", "project_id", "source_type"),
        Index("ix_research_records_project_collected_at", "project_id", "collected_at"),
    )


class GrowthOpportunity(Base):
    __tablename__ = "growth_opportunities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", server_default="draft"
    )
    estimated_impact: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", server_default="medium"
    )
    estimated_effort: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", server_default="medium"
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="p2_medium", server_default="p2_medium"
    )
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_growth_opportunities_id_project"),
        UniqueConstraint("project_id", "slug", name="uq_growth_opportunities_project_slug"),
        CheckConstraint(
            "category IN ('acquisition', 'activation', 'retention', 'referral', 'revenue', 'experimentation')",
            name="ck_growth_opportunities_category",
        ),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'rejected', 'archived')",
            name="ck_growth_opportunities_status",
        ),
        CheckConstraint(
            "estimated_impact IN ('low', 'medium', 'high', 'critical')",
            name="ck_growth_opportunities_estimated_impact",
        ),
        CheckConstraint(
            "estimated_effort IN ('low', 'medium', 'high')",
            name="ck_growth_opportunities_estimated_effort",
        ),
        CheckConstraint(
            "priority IN ('p0_urgent', 'p1_high', 'p2_medium', 'p3_low')",
            name="ck_growth_opportunities_priority",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.00 AND confidence_score <= 1.00)",
            name="ck_growth_opportunities_confidence",
        ),
        Index("ix_growth_opportunities_project_status", "project_id", "status"),
        Index("ix_growth_opportunities_project_category", "project_id", "category"),
        Index("ix_growth_opportunities_project_priority", "project_id", "priority"),
    )


class OpportunityStatusHistory(Base):
    __tablename__ = "opportunity_status_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    opportunity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    system_metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "system_metadata_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["opportunity_id", "project_id"],
            ["growth_opportunities.id", "growth_opportunities.project_id"],
            name="fk_history_opportunity_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "new_status IN ('draft', 'in_review', 'approved', 'rejected', 'archived')",
            name="ck_history_new_status",
        ),
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('draft', 'in_review', 'approved', 'rejected', 'archived')",
            name="ck_history_previous_status",
        ),
        Index("ix_opportunity_status_history_opp_created", "opportunity_id", "created_at"),
        Index("ix_opportunity_status_history_project", "project_id", "created_at"),
    )


class OpportunityResearchAssociation(Base):
    __tablename__ = "opportunity_research_associations"

    opportunity_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["opportunity_id", "project_id"],
            ["growth_opportunities.id", "growth_opportunities.project_id"],
            name="fk_assoc_opportunity_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["research_id", "project_id"],
            ["research_records.id", "research_records.project_id"],
            name="fk_assoc_research_project",
            ondelete="CASCADE",
        ),
        Index("ix_assoc_research_id", "research_id"),
        Index("ix_assoc_project_id", "project_id"),
    )


class GrowthStrategy(Base):
    __tablename__ = "growth_strategies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategic_vision: Mapped[str] = mapped_column(Text, nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    strategic_constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget_envelope: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD", server_default="USD"
    )
    time_horizon: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", server_default="draft"
    )
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_growth_strategies_id_project"),
        UniqueConstraint("project_id", "slug", name="uq_growth_strategies_project_slug"),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'active', 'completed', 'archived')",
            name="ck_growth_strategies_status",
        ),
        CheckConstraint(
            "budget_envelope IS NULL OR budget_envelope >= 0.00",
            name="ck_growth_strategies_budget",
        ),
        CheckConstraint(
            "length(currency) = 3",
            name="ck_growth_strategies_currency",
        ),
        Index("ix_growth_strategies_project_status", "project_id", "status"),
        Index("ix_growth_strategies_project_time_horizon", "project_id", "time_horizon"),
    )


class StrategyGoal(Base):
    __tablename__ = "strategy_goals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    baseline_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending"
    )
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["strategy_id", "project_id"],
            ["growth_strategies.id", "growth_strategies.project_id"],
            name="fk_strategy_goals_strategy_project",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "project_id", name="uq_strategy_goals_id_project"),
        CheckConstraint(
            "status IN ('pending', 'on_track', 'at_risk', 'behind', 'achieved', 'abandoned')",
            name="ck_strategy_goals_status",
        ),
        Index("ix_strategy_goals_strategy_status", "strategy_id", "status"),
        Index("ix_strategy_goals_project_status", "project_id", "status"),
    )


class StrategyOpportunityAssociation(Base):
    __tablename__ = "strategy_opportunity_associations"

    strategy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    strategic_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["strategy_id", "project_id"],
            ["growth_strategies.id", "growth_strategies.project_id"],
            name="fk_assoc_strat_strategy_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "project_id"],
            ["growth_opportunities.id", "growth_opportunities.project_id"],
            name="fk_assoc_strat_opportunity_project",
            ondelete="CASCADE",
        ),
        Index("ix_assoc_strat_opportunity_id", "opportunity_id"),
        Index("ix_assoc_strat_project_id", "project_id"),
    )


class StrategyStatusHistory(Base):
    __tablename__ = "strategy_status_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    system_metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "system_metadata_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["strategy_id", "project_id"],
            ["growth_strategies.id", "growth_strategies.project_id"],
            name="fk_strat_history_strategy_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "new_status IN ('draft', 'in_review', 'approved', 'active', 'completed', 'archived')",
            name="ck_strategy_history_new_status",
        ),
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('draft', 'in_review', 'approved', 'active', 'completed', 'archived')",
            name="ck_strategy_history_previous_status",
        ),
        Index("ix_strategy_status_history_strat_created", "strategy_id", "created_at"),
        Index("ix_strategy_status_history_project", "project_id", "created_at"),
    )


class GoalMetricUpdate(Base):
    __tablename__ = "goal_metric_updates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    goal_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    new_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "project_id"],
            ["strategy_goals.id", "strategy_goals.project_id"],
            name="fk_metric_update_goal_project",
            ondelete="RESTRICT",
        ),
        Index("ix_goal_metric_updates_goal_created", "goal_id", "created_at"),
        Index("ix_goal_metric_updates_project", "project_id", "created_at"),
    )
