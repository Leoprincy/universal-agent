"""Contracts for Phase 8 operational monitoring."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WorkerInfo(BaseModel):
    worker_id: str
    last_seen: str | None = None
    age_seconds: float
    alive: bool
    concurrency: int | None = None
    jobs_completed: int | None = None
    jobs_failed: int | None = None


class OpsOverviewResponse(BaseModel):
    workers: list[WorkerInfo]
    worker_heartbeat_store: str
    active_workers: int
    queue_depth: int | None
    jobs: dict[str, int]
    outbox: dict[str, int]
    expired_leases: int
    retries: dict[str, int]
    schedules: list[dict[str, Any]]
