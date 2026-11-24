import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
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


class GoalStatusHistory(Base):
    __tablename__ = "goal_status_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    goal_id: Mapped[str] = mapped_column(String(36), nullable=False)
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
            ["goal_id", "project_id"],
            ["strategy_goals.id", "strategy_goals.project_id"],
            name="fk_goal_history_goal_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "new_status IN ('pending', 'on_track', 'at_risk', 'behind', 'achieved', 'abandoned')",
            name="ck_goal_history_new_status",
        ),
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('pending', 'on_track', 'at_risk', 'behind', 'achieved', 'abandoned')",
            name="ck_goal_history_previous_status",
        ),
        Index("ix_goal_status_history_goal_created", "goal_id", "created_at"),
        Index("ix_goal_status_history_project", "project_id", "created_at"),
    )


class IntegrationProvider(Base):
    __tablename__ = "integration_providers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sandbox_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    config_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "config_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
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
        UniqueConstraint("project_id", "name", name="uq_integration_provider_project_name"),
        UniqueConstraint("id", "project_id", name="uq_integration_provider_id_project"),
        ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_integration_provider_project", ondelete="CASCADE"
        ),
        CheckConstraint("rate_limit_per_minute > 0", name="ck_integration_provider_rate_limit"),
        Index("ix_integration_providers_project", "project_id", "created_at"),
    )


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
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
        UniqueConstraint("provider_id", name="uq_integration_credential_provider"),
        ForeignKeyConstraint(
            ["provider_id", "project_id"],
            ["integration_providers.id", "integration_providers.project_id"],
            name="fk_credential_provider_project",
            ondelete="RESTRICT",
        ),
    )


class IntegrationAction(Base):
    __tablename__ = "integration_actions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        "payload_json", JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval", nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    approver: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pending_approval_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    approval_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "result_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        UniqueConstraint(
            "provider_id", "idempotency_key", name="uq_integration_action_idempotency"
        ),
        UniqueConstraint("id", "project_id", name="uq_integration_action_id_project"),
        ForeignKeyConstraint(
            ["provider_id", "project_id"],
            ["integration_providers.id", "integration_providers.project_id"],
            name="fk_action_provider_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected', 'expired', 'executing', 'succeeded', 'failed', 'cancelled')",
            name="ck_integration_action_status",
        ),
        Index("ix_integration_actions_project_status", "project_id", "status"),
        Index("ix_integration_actions_provider_status", "provider_id", "status"),
    )


class IntegrationActionEvent(Base):
    __tablename__ = "integration_action_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    detail_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "detail_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["action_id", "project_id"],
            ["integration_actions.id", "integration_actions.project_id"],
            name="fk_action_event_action_project",
            ondelete="RESTRICT",
        ),
        Index("ix_integration_action_events_action", "action_id", "created_at"),
        Index("ix_integration_action_events_project", "project_id", "created_at"),
    )


class IntegrationCallLog(Base):
    __tablename__ = "integration_call_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["action_id", "project_id"],
            ["integration_actions.id", "integration_actions.project_id"],
            name="fk_call_log_action_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint("mode IN ('sandbox', 'live')", name="ck_call_log_mode"),
        Index("ix_integration_call_logs_action", "action_id", "created_at"),
        Index("ix_integration_call_logs_provider_created", "provider_id", "created_at"),
    )


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False)
    goal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_criteria_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "success_criteria_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        UniqueConstraint("id", "project_id", name="uq_experiments_id_project"),
        ForeignKeyConstraint(
            ["strategy_id", "project_id"],
            ["growth_strategies.id", "growth_strategies.project_id"],
            name="fk_experiments_strategy_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["goal_id", "project_id"],
            ["strategy_goals.id", "strategy_goals.project_id"],
            name="fk_experiments_goal_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'running', 'completed', 'cancelled')",
            name="ck_experiments_status",
        ),
        Index("ix_experiments_strategy_status", "strategy_id", "status"),
        Index("ix_experiments_project_status", "project_id", "status"),
        Index("ix_experiments_project_created", "project_id", "created_at"),
    )


class ExperimentStatusHistory(Base):
    __tablename__ = "experiment_status_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
            ["experiment_id", "project_id"],
            ["experiments.id", "experiments.project_id"],
            name="fk_exp_history_experiment_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "new_status IN ('draft', 'in_review', 'running', 'completed', 'cancelled')",
            name="ck_exp_history_new_status",
        ),
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('draft', 'in_review', 'running', 'completed', 'cancelled')",
            name="ck_exp_history_previous_status",
        ),
        UniqueConstraint("experiment_id", "seq", name="uq_exp_history_exp_seq"),
        Index("ix_exp_history_experiment_created", "experiment_id", "created_at"),
        Index("ix_exp_history_experiment_seq", "experiment_id", "seq"),
        Index("ix_exp_history_project", "project_id", "created_at"),
    )


class ExperimentOutcome(Base):
    __tablename__ = "experiment_outcomes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_exp_outcomes_id_project"),
        ForeignKeyConstraint(
            ["experiment_id", "project_id"],
            ["experiments.id", "experiments.project_id"],
            name="fk_exp_outcome_experiment_project",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_id", "project_id"],
            ["experiment_outcomes.id", "experiment_outcomes.project_id"],
            name="fk_exp_outcome_supersedes_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source IN ('manual', 'integration', 'import')",
            name="ck_exp_outcome_source",
        ),
        Index("ix_exp_outcomes_experiment_created", "experiment_id", "created_at"),
        Index("ix_exp_outcomes_project", "project_id", "created_at"),
        Index("ix_exp_outcomes_metric", "experiment_id", "metric_name"),
    )


class ExperimentEvaluation(Base):
    __tablename__ = "experiment_evaluations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "rationale_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["experiment_id", "project_id"],
            ["experiments.id", "experiments.project_id"],
            name="fk_exp_eval_experiment_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "verdict IN ('succeeded', 'inconclusive', 'failed')",
            name="ck_exp_eval_verdict",
        ),
        Index("ix_exp_evals_experiment_created", "experiment_id", "created_at"),
        Index("ix_exp_evals_project", "project_id", "created_at"),
    )


class LearningRecord(Base):
    __tablename__ = "learning_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    experiment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    insight: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="candidate", nullable=False)
    evidence_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "evidence_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    validated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        UniqueConstraint("id", "project_id", name="uq_learning_records_id_project"),
        ForeignKeyConstraint(
            ["strategy_id", "project_id"],
            ["growth_strategies.id", "growth_strategies.project_id"],
            name="fk_learning_strategy_project",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["experiment_id", "project_id"],
            ["experiments.id", "experiments.project_id"],
            name="fk_learning_experiment_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('candidate', 'validated', 'rejected')",
            name="ck_learning_records_status",
        ),
        Index("ix_learning_records_project_status", "project_id", "status"),
        Index("ix_learning_records_experiment", "experiment_id"),
    )


class Job(Base):
    """Persistent background job record (Phase 8).

    PostgreSQL is the durable source of truth; Redis carries only job ID
    references for queue delivery.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "payload_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
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
        UniqueConstraint("id", "project_id", name="uq_jobs_id_project"),
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_jobs_project_idempotency"
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_jobs_project",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts"),
        Index("ix_jobs_project_status", "project_id", "status"),
        Index("ix_jobs_project_created", "project_id", "created_at"),
        Index("ix_jobs_dispatch", "status", "scheduled_at"),
        Index("ix_jobs_job_type", "job_type"),
    )


class JobEvent(Base):
    """Append-only job lifecycle audit log (Phase 8)."""

    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("job_id", "seq", name="uq_job_events_job_seq"),
        ForeignKeyConstraint(
            ["job_id", "project_id"],
            ["jobs.id", "jobs.project_id"],
            name="fk_job_events_job_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "event_type IN ('created', 'queued', 'started', 'completed', 'failed', 'cancelled', 'requeued')",
            name="ck_job_events_type",
        ),
        Index("ix_job_events_job_seq", "job_id", "seq"),
        Index("ix_job_events_project", "project_id", "created_at"),
    )


class JobOutboxEvent(Base):
    """Transactional outbox row for job dispatch (Phase 8).

    Written in the same transaction as the job state change; a publisher
    drains pending rows to the queue independently, making dispatch
    recoverable after crashes.
    """

    __tablename__ = "job_outbox_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "project_id"],
            ["jobs.id", "jobs.project_id"],
            name="fk_job_outbox_job_project",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pending', 'published', 'failed')",
            name="ck_job_outbox_status",
        ),
        Index("ix_job_outbox_status_created", "status", "created_at"),
        Index("ix_job_outbox_project", "project_id", "created_at"),
    )


class JobSchedule(Base):
    """Persistent recurring job schedule (Phase 8).

    Interval-based (no cron dependency). The scheduler materializes each due
    occurrence as a Job whose idempotency_key encodes the schedule slot,
    preventing duplicate occurrences across restarts.
    """

    __tablename__ = "job_schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "payload_json", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
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
        UniqueConstraint("project_id", "name", name="uq_job_schedules_project_name"),
        ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_job_schedules_project",
            ondelete="CASCADE",
        ),
        CheckConstraint("interval_seconds > 0", name="ck_job_schedules_interval"),
        Index("ix_job_schedules_due", "enabled", "next_run_at"),
        Index("ix_job_schedules_project", "project_id"),
    )
