from datetime import datetime
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

OpportunityCategory = Literal[
    "acquisition",
    "activation",
    "retention",
    "referral",
    "revenue",
    "experimentation",
]
OpportunityStatus = Literal["draft", "in_review", "approved", "rejected", "archived"]
OpportunityImpact = Literal["low", "medium", "high", "critical"]
OpportunityEffort = Literal["low", "medium", "high"]
OpportunityPriority = Literal["p0_urgent", "p1_high", "p2_medium", "p3_low"]

PRIORITY_MATRIX: dict[tuple[OpportunityImpact, OpportunityEffort], OpportunityPriority] = {
    ("critical", "low"): "p0_urgent",
    ("critical", "medium"): "p0_urgent",
    ("critical", "high"): "p1_high",
    ("high", "low"): "p0_urgent",
    ("high", "medium"): "p1_high",
    ("high", "high"): "p2_medium",
    ("medium", "low"): "p1_high",
    ("medium", "medium"): "p2_medium",
    ("medium", "high"): "p3_low",
    ("low", "low"): "p2_medium",
    ("low", "medium"): "p3_low",
    ("low", "high"): "p3_low",
}


def calculate_priority(impact: OpportunityImpact, effort: OpportunityEffort) -> OpportunityPriority:
    key = (impact, effort)
    if key not in PRIORITY_MATRIX:
        raise ValueError(f"Exhaustive priority check failed: unsupported combination {key}")
    return PRIORITY_MATRIX[key]


class OpportunityBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=200)
    problem_statement: str = Field(..., min_length=1)
    hypothesis: str = Field(..., min_length=1)
    proposed_mechanism: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    category: OpportunityCategory
    estimated_impact: OpportunityImpact = "medium"
    estimated_effort: OpportunityEffort = "medium"
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class OpportunityCreate(OpportunityBase):
    slug: str | None = Field(default=None, max_length=220)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens (e.g. 'one-tap-apply')")
        return v


class OpportunityUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    problem_statement: str | None = Field(default=None, min_length=1)
    hypothesis: str | None = Field(default=None, min_length=1)
    proposed_mechanism: str | None = Field(default=None, min_length=1)
    target_audience: str | None = Field(default=None, min_length=1)
    category: OpportunityCategory | None = None
    status: OpportunityStatus | None = None
    estimated_impact: OpportunityImpact | None = None
    estimated_effort: OpportunityEffort | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None  # Passed when status is also updated in PATCH
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class OpportunityTransition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: OpportunityStatus
    reason: str | None = None
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class OpportunityResponse(OpportunityBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    project_id: str
    slug: str
    status: OpportunityStatus
    priority: OpportunityPriority
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    total: int
    limit: int = 50
    offset: int = 0
