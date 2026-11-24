from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.strategy import StrategyStatus


class StrategyStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    strategy_id: str
    project_id: str
    previous_status: StrategyStatus | None = None
    new_status: StrategyStatus
    reason: str | None = None
    actor: str
    system_metadata_json: dict[str, Any] | None = Field(default=None, alias="system_metadata")
    created_at: datetime


class StrategyStatusHistoryListResponse(BaseModel):
    items: list[StrategyStatusHistoryResponse]
    total: int
