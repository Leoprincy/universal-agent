from datetime import datetime
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

StrategyStatus = Literal["draft", "in_review", "approved", "active", "completed", "archived"]


class GrowthStrategyBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    strategic_vision: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    strategic_constraints: str | None = None
    budget_envelope: float | None = Field(default=None, ge=0.0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    time_horizon: str = Field(..., min_length=1, max_length=50)
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        code = v.strip().upper()
        if not re.match(r"^[A-Z]{3}$", code):
            raise ValueError("Currency must be a valid 3-letter ISO-4217 code (e.g. 'USD', 'EUR')")
        return code


class GrowthStrategyCreate(GrowthStrategyBase):
    slug: str | None = Field(default=None, max_length=220)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens (e.g. 'q1-activation')")
        return v


class GrowthStrategyUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    strategic_vision: str | None = Field(default=None, min_length=1)
    target_audience: str | None = Field(default=None, min_length=1)
    strategic_constraints: str | None = None
    budget_envelope: float | None = Field(default=None, ge=0.0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    time_horizon: str | None = Field(default=None, min_length=1, max_length=50)
    status: StrategyStatus | None = None
    reason: str | None = None
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return None
        code = v.strip().upper()
        if not re.match(r"^[A-Z]{3}$", code):
            raise ValueError("Currency must be a valid 3-letter ISO-4217 code")
        return code


class GrowthStrategyTransition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: StrategyStatus
    reason: str | None = None
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class GrowthStrategyResponse(GrowthStrategyBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    project_id: str
    slug: str
    status: StrategyStatus
    created_at: datetime
    updated_at: datetime


class GrowthStrategyListResponse(BaseModel):
    items: list[GrowthStrategyResponse]
    total: int
    limit: int
    offset: int
