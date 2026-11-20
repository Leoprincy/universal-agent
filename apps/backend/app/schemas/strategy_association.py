from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.opportunity import OpportunityResponse


class StrategyOpportunityAssociateItem(BaseModel):
    opportunity_id: str
    strategic_rationale: str | None = None


class StrategyOpportunityAssociateRequest(BaseModel):
    items: list[StrategyOpportunityAssociateItem] = Field(..., min_length=1)


class StrategyOpportunityAssociationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_id: str
    opportunity_id: str
    project_id: str
    strategic_rationale: str | None = None
    created_at: datetime


class AssociatedOpportunityItem(BaseModel):
    strategy_id: str
    opportunity_id: str
    project_id: str
    strategic_rationale: str | None = None
    created_at: datetime
    opportunity: OpportunityResponse


class StrategyOpportunityListResponse(BaseModel):
    items: list[AssociatedOpportunityItem]
    total: int
