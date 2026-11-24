"""Pydantic contracts for Phase 8 persistent jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal["pending", "queued", "running", "completed", "failed", "cancelled"]


class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] | None = None
    priority: int = Field(default=0, ge=-100, le=100)
    scheduled_at: datetime | None = None
    max_attempts: int = Field(default=3, ge=1, le=100)
    idempotency_key: str | None = Field(default=None, max_length=200)
    correlation_id: str | None = Field(default=None, max_length=100)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    job_type: str
    payload: dict[str, Any] | None = Field(default=None, alias="payload_json")
    status: str
    priority: int
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt_count: int
    max_attempts: int
    last_error: str | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None
    locked_by: str | None = None
    locked_until: datetime | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    limit: int
    offset: int


class JobEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    project_id: str
    seq: int
    event_type: str
    from_status: str | None = None
    to_status: str
    message: str | None = None
    actor: str
    created_at: datetime


class JobScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    job_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] | None = None
    interval_seconds: int = Field(gt=0, le=31_536_000)
    next_run_at: datetime | None = None

    @field_validator("job_type")
    @classmethod
    def _job_type(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("job_type must not be empty")
        return v


class JobScheduleResponse(BaseModel):
    id: str
    project_id: str
    name: str
    job_type: str
    payload: dict[str, Any] | None
    interval_seconds: int
    next_run_at: datetime
    last_run_at: datetime | None
    enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class JobScheduleListResponse(BaseModel):
    items: list[JobScheduleResponse]
    total: int


class JobScheduleToggle(BaseModel):
    enabled: bool


class JobStatsResponse(BaseModel):
    pending: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    with_retries: int
