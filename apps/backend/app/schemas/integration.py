"""Pydantic contracts for Phase 6 integration providers and actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IntegrationActionStatus = Literal[
    "pending_approval",
    "approved",
    "rejected",
    "expired",
    "executing",
    "succeeded",
    "failed",
    "cancelled",
]


class IntegrationProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    adapter_type: str = Field(min_length=1, max_length=50, default="sandbox")
    enabled: bool = True
    sandbox_only: bool = True
    rate_limit_per_minute: int = Field(default=60, gt=0)
    config: dict[str, Any] | None = None


class IntegrationProviderUpdate(BaseModel):
    enabled: bool | None = None
    sandbox_only: bool | None = None
    rate_limit_per_minute: int | None = Field(default=None, gt=0)
    config: dict[str, Any] | None = None


class IntegrationProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    adapter_type: str
    enabled: bool
    sandbox_only: bool
    rate_limit_per_minute: int
    config: dict[str, Any] | None = None
    has_credential: bool = False
    created_at: datetime
    updated_at: datetime


class CredentialSetInput(BaseModel):
    """Write-only credential payload. The secret is never returned by the API."""

    credential: str = Field(min_length=1)


class IntegrationActionCreate(BaseModel):
    action_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class IntegrationActionDecisionInput(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class IntegrationActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    provider_id: str
    action_type: str
    payload: dict[str, Any]
    payload_hash: str
    status: str
    idempotency_key: str | None = None
    actor: str
    approver: str | None = None
    decision_reason: str | None = None
    pending_approval_expires_at: datetime
    approval_expires_at: datetime | None = None
    decided_at: datetime | None = None
    executed_at: datetime | None = None
    attempt_count: int
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationActionListResponse(BaseModel):
    items: list[IntegrationActionResponse]
    total: int


class IntegrationActionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action_id: str
    project_id: str
    event_type: str
    actor: str
    detail: dict[str, Any] | None = None
    seq: int = 0
    created_at: datetime


class IntegrationCallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action_id: str
    project_id: str
    provider_id: str
    attempt: int
    mode: str
    status: str
    response_status: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    created_at: datetime
