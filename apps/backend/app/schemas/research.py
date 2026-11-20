from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal[
    "user_interview",
    "app_review",
    "competitor_analysis",
    "analytics",
    "market_report",
    "manual_observation",
]


class ResearchRecordBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=200)
    source_type: SourceType
    source_url: str | None = Field(default=None, max_length=2048)
    source_name: str | None = Field(default=None, max_length=120)
    author: str | None = Field(default=None, max_length=120)
    source_quote: str | None = None
    observation_summary: str = Field(..., min_length=1)
    interpretation_notes: str | None = None
    evidence_data: dict[str, Any] | None = None
    observed_at: datetime | None = None
    published_at: datetime | None = None
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")

    @model_validator(mode="after")
    def validate_source_type_requirements(self) -> "ResearchRecordBase":
        st = self.source_type
        if st == "user_interview":
            if not self.source_name or not self.source_name.strip():
                raise ValueError("user_interview requires source_name (e.g. participant identifier/role/cohort)")
            if not self.observation_summary or not self.observation_summary.strip():
                raise ValueError("user_interview requires observation_summary")

        elif st == "app_review":
            if not self.source_name or not self.source_name.strip():
                raise ValueError("app_review requires source_name (e.g. Google Play, App Store)")
            if not self.source_quote or not self.source_quote.strip():
                raise ValueError("app_review requires verbatim source_quote")
            if not self.observation_summary or not self.observation_summary.strip():
                raise ValueError("app_review requires observation_summary")

        elif st == "competitor_analysis":
            has_url = bool(self.source_url and self.source_url.strip())
            has_name = bool(self.source_name and self.source_name.strip())
            if not (has_url or has_name):
                raise ValueError("competitor_analysis requires at least one of source_url or source_name")
            if not self.observation_summary or not self.observation_summary.strip():
                raise ValueError("competitor_analysis requires observation_summary")

        elif st == "analytics":
            if not self.evidence_data or not isinstance(self.evidence_data, dict) or len(self.evidence_data) == 0:
                raise ValueError("analytics requires non-empty evidence_data metrics dictionary")
            has_numeric = any(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in self.evidence_data.values()
            )
            if not has_numeric:
                raise ValueError("analytics evidence_data must contain at least one numeric metric observation")
            if not self.observation_summary or not self.observation_summary.strip():
                raise ValueError("analytics requires observation_summary")

        elif st == "market_report":
            if not self.source_name or not self.source_name.strip():
                raise ValueError("market_report requires source_name (publishing entity)")
            if not self.observation_summary or not self.observation_summary.strip():
                raise ValueError("market_report requires observation_summary")
            has_url = bool(self.source_url and self.source_url.strip())
            has_author = bool(self.author and self.author.strip())
            if not (has_url or has_author):
                raise ValueError("market_report requires at least one of source_url or author")

        elif st == "manual_observation":
            if not self.observation_summary or not self.observation_summary.strip():
                raise ValueError("manual_observation requires observation_summary")

        return self


class ResearchRecordCreate(ResearchRecordBase):
    pass


class ResearchRecordUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: SourceType | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    source_name: str | None = Field(default=None, max_length=120)
    author: str | None = Field(default=None, max_length=120)
    source_quote: str | None = None
    observation_summary: str | None = Field(default=None, min_length=1)
    interpretation_notes: str | None = None
    evidence_data: dict[str, Any] | None = None
    observed_at: datetime | None = None
    published_at: datetime | None = None
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")


class ResearchRecordResponse(ResearchRecordBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    project_id: str
    collected_at: datetime
    created_at: datetime
    updated_at: datetime


class ResearchRecordListResponse(BaseModel):
    items: list[ResearchRecordResponse]
    total: int
    limit: int = 50
    offset: int = 0
