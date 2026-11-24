from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

GoalStatus = Literal["pending", "on_track", "at_risk", "behind", "achieved", "abandoned"]


def compute_goal_progress(baseline: float, target: float, current: float) -> tuple[float, bool]:
    """Calculate progress percentage and determine metric direction.

    Handles both:
    1. Increasing metrics (target > baseline): higher values represent improvement.
    2. Decreasing metrics (target < baseline): lower values represent improvement.
    3. Flat metrics (target == baseline): division by zero safeguard.
    """
    if target > baseline:
        is_increasing = True
        span = target - baseline
        progress = ((current - baseline) / span) * 100.0
    elif target < baseline:
        is_increasing = False
        span = baseline - target
        progress = ((baseline - current) / span) * 100.0
    else:
        is_increasing = True
        progress = 100.0 if current >= target else 0.0
    return round(progress, 2), is_increasing


class StrategyGoalBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    metric_name: str = Field(..., min_length=1, max_length=100)
    metric_unit: str = Field(..., min_length=1, max_length=50)
    baseline_value: float
    target_value: float
    current_value: float | None = None
    deadline: datetime | None = None
    status: GoalStatus = "pending"
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class StrategyGoalCreate(StrategyGoalBase):
    @model_validator(mode="after")
    def validate_initial_status_pending(self) -> "StrategyGoalCreate":
        if self.status != "pending":
            raise ValueError(
                "New goals must start in 'pending' status; use goal updates to change status"
            )
        return self


class StrategyGoalUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    metric_name: str | None = Field(default=None, min_length=1, max_length=100)
    metric_unit: str | None = Field(default=None, min_length=1, max_length=50)
    baseline_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    deadline: datetime | None = None
    status: GoalStatus | None = None
    reason: str | None = None  # Recorded in status history when status changes
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class StrategyGoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    project_id: str
    strategy_id: str
    name: str
    description: str | None = None
    metric_name: str
    metric_unit: str
    baseline_value: float
    current_value: float
    target_value: float
    deadline: datetime | None = None
    status: GoalStatus
    progress_percentage: float | None = None
    is_increasing_metric: bool = True
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class StrategyGoalListResponse(BaseModel):
    items: list[StrategyGoalResponse]
    total: int


class GoalMetricUpdateCreate(BaseModel):
    new_value: float
    notes: str | None = None


class GoalMetricUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    project_id: str
    previous_value: float
    new_value: float
    notes: str | None = None
    actor: str
    created_at: datetime


class GoalMetricHistoryListResponse(BaseModel):
    items: list[GoalMetricUpdateResponse]
    total: int


class GoalStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    goal_id: str
    project_id: str
    previous_status: GoalStatus | None = None
    new_status: GoalStatus
    reason: str | None = None
    actor: str
    system_metadata_json: dict[str, Any] | None = Field(default=None, alias="system_metadata")
    created_at: datetime


class GoalStatusHistoryListResponse(BaseModel):
    items: list[GoalStatusHistoryResponse]
    total: int
