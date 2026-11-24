"""Pydantic contracts for Phase 7 experiments, outcomes, and evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ExperimentStatus = Literal["draft", "in_review", "running", "completed", "cancelled"]
OutcomeSource = Literal["manual", "integration", "import"]
EvaluationVerdict = Literal["succeeded", "inconclusive", "failed"]
Comparator = Literal["gt", "gte", "lt", "lte"]


class SuccessCriterion(BaseModel):
    """One deterministic success criterion for an experiment."""

    metric_name: str = Field(min_length=1, max_length=100)
    comparator: Comparator
    threshold: float
    min_sample_size: int | None = Field(default=None, ge=0)
    window_days: int | None = Field(default=None, gt=0)


class SuccessCriteria(BaseModel):
    criteria: list[SuccessCriterion] = Field(min_length=1)

    @field_validator("criteria")
    @classmethod
    def _unique_metrics(cls, v: list[SuccessCriterion]) -> list[SuccessCriterion]:
        names = [c.metric_name for c in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate metric_name in success criteria")
        return v


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str | None = Field(default=None, max_length=4000)
    goal_id: str | None = None
    success_criteria: SuccessCriteria | None = None
    ends_at: datetime | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hypothesis: str | None = Field(default=None, max_length=4000)
    goal_id: str | None = None
    success_criteria: SuccessCriteria | None = None
    ends_at: datetime | None = None


class ExperimentTransition(BaseModel):
    status: ExperimentStatus
    reason: str | None = Field(default=None, max_length=2000)


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    strategy_id: str
    goal_id: str | None = None
    name: str
    hypothesis: str | None = None
    success_criteria: dict[str, Any] | None = None
    status: str
    started_at: datetime | None = None
    ends_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ExperimentListResponse(BaseModel):
    items: list[ExperimentResponse]
    total: int


class ExperimentOutcomeCreate(BaseModel):
    metric_name: str = Field(min_length=1, max_length=100)
    value: float
    sample_size: int | None = Field(default=None, ge=0)
    observed_at: datetime
    source: OutcomeSource = "manual"
    source_ref: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    supersedes_id: str | None = None


class ExperimentOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_id: str
    project_id: str
    metric_name: str
    value: float
    sample_size: int | None = None
    observed_at: datetime
    source: str
    source_ref: str | None = None
    notes: str | None = None
    actor: str
    supersedes_id: str | None = None
    created_at: datetime


class ExperimentEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_id: str
    project_id: str
    verdict: str
    rationale: dict[str, Any] | None = None
    evaluated_at: datetime
    actor: str
    created_at: datetime


class ExperimentStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_id: str
    project_id: str
    previous_status: str | None = None
    new_status: str
    reason: str | None = None
    actor: str
    system_metadata: dict[str, Any] | None = Field(default=None, alias="system_metadata_json")
    created_at: datetime
