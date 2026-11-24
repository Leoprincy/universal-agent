"""Pydantic contracts for Phase 7 learning records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LearningStatus = Literal["candidate", "validated", "rejected"]


class LearningEvidence(BaseModel):
    """References to supporting records. All IDs are verified server-side."""

    outcome_ids: list[str] = Field(default_factory=list, max_length=100)
    evaluation_ids: list[str] = Field(default_factory=list, max_length=100)


class LearningCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    insight: str = Field(min_length=1, max_length=8000)
    category: str | None = Field(default=None, max_length=50)
    strategy_id: str | None = None
    experiment_id: str | None = None
    evidence: LearningEvidence | None = None


class LearningUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    insight: str | None = Field(default=None, min_length=1, max_length=8000)
    category: str | None = Field(default=None, max_length=50)
    strategy_id: str | None = None
    experiment_id: str | None = None
    evidence: LearningEvidence | None = None


class LearningReject(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class LearningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    strategy_id: str | None = None
    experiment_id: str | None = None
    title: str
    insight: str
    category: str | None = None
    status: str
    evidence: dict[str, Any] | None = Field(default=None, alias="evidence_json")
    validated_by: str | None = None
    validated_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class LearningListResponse(BaseModel):
    items: list[LearningResponse]
    total: int
