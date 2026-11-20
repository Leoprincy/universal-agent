from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.research import ResearchRecordResponse


class AssociationItem(BaseModel):
    research_id: str
    notes: str | None = None


class AssociateResearchRequest(BaseModel):
    items: list[AssociationItem]


class AssociatedResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    research_id: str
    opportunity_id: str
    project_id: str
    notes: str | None = None
    created_at: datetime
    research: ResearchRecordResponse | None = None


class AssociateResearchResponse(BaseModel):
    linked_count: int
    items: list[AssociatedResearchResponse]
