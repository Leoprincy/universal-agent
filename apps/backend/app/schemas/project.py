from datetime import datetime
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectCategory = Literal["mobile_app", "web_app", "saas", "ecommerce", "other"]
ProjectStatus = Literal["active", "paused", "archived"]


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: ProjectCategory = "other"
    target_audience: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


class ProjectCreate(ProjectBase):
    slug: str | None = Field(default=None, max_length=140)
    owner: str | None = Field(default=None, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens (e.g. 'my-app')")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: ProjectCategory | None = None
    status: ProjectStatus | None = None
    target_audience: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    owner: str = "default"
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    limit: int = 50
    offset: int = 0
