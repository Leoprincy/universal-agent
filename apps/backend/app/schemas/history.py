from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class OpportunityStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    opportunity_id: str
    project_id: str
    previous_status: str | None = None
    new_status: str
    reason: str | None = None
    actor: str
    system_metadata_json: dict[str, Any] | None = Field(default=None, alias="system_metadata")
    created_at: datetime


class OpportunityStatusHistoryListResponse(BaseModel):
    items: list[OpportunityStatusHistoryResponse]
    total: int
