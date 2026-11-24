"""Phase 8 operational monitoring service (read-only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Job,
    JobOutboxEvent,
    JobSchedule,
)
from app.jobs.queue import JobQueue, QueueUnavailableError

WORKER_STALE_SECONDS = 180
WORKERS_KEY = "uga:workers"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class OpsService:
    def __init__(self, session: Session, queue: JobQueue, redis_client: Any = None) -> None:
        self._session = session
        self._queue = queue
        self._redis = redis_client

    # ── workers ───────────────────────────────────────────────────────────

    async def list_workers(self) -> tuple[list[dict[str, Any]], bool]:
        """Worker heartbeats from Redis. Returns (workers, store_available)."""
        if self._redis is None:
            return [], False
        try:
            raw = await self._redis.hgetall(WORKERS_KEY)
        except Exception:
            return [], False
        now = _utcnow()
        workers = []
        for wid, blob in (raw or {}).items():
            try:
                info = json.loads(blob)
            except (TypeError, ValueError):
                continue
            try:
                seen = _aware(datetime.fromisoformat(info.get("last_seen", "")))
            except ValueError:
                continue
            age = (now - seen).total_seconds()
            workers.append({
                "worker_id": info.get("worker_id", wid),
                "last_seen": info.get("last_seen"),
                "age_seconds": round(age, 1),
                "alive": age <= WORKER_STALE_SECONDS,
                "concurrency": info.get("concurrency"),
                "jobs_completed": info.get("jobs_completed"),
                "jobs_failed": info.get("jobs_failed"),
            })
        workers.sort(key=lambda w: w["age_seconds"])
        return workers, True

    # ── queue / outbox / jobs ─────────────────────────────────────────────

    async def queue_depth(self) -> int | None:
        try:
            return await self._queue.depth()
        except QueueUnavailableError:
            return None

    def job_counts(self) -> dict[str, int]:
        rows = self._session.execute(
            select(Job.status, func.count()).group_by(Job.status)
        ).all()
        counts = {s: 0 for s in
                  ("pending", "queued", "running", "completed", "failed", "cancelled")}
        for status, n in rows:
            counts[status] = n
        return counts

    def outbox_counts(self) -> dict[str, int]:
        rows = self._session.execute(
            select(JobOutboxEvent.status, func.count()).group_by(JobOutboxEvent.status)
        ).all()
        counts = {"pending": 0, "published": 0, "failed": 0}
        for status, n in rows:
            counts[status] = n
        return counts

    def expired_leases(self) -> int:
        now = _utcnow()
        return self._session.scalar(
            select(func.count()).select_from(Job).where(
                (Job.status == "running")
                & (Job.locked_until.isnot(None))
                & (Job.locked_until < now)
            )
        ) or 0

    def retry_activity(self) -> dict[str, int]:
        return {
            "jobs_with_retries": self._session.scalar(
                select(func.count()).select_from(Job).where(Job.attempt_count > 1)
            ) or 0,
            "total_attempts": self._session.scalar(
                select(func.coalesce(func.sum(Job.attempt_count), 0)).select_from(Job)
            ) or 0,
        }

    def schedule_summary(self) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(JobSchedule).order_by(JobSchedule.next_run_at)
        ).all()
        return [{
            "id": s.id,
            "project_id": s.project_id,
            "name": s.name,
            "job_type": s.job_type,
            "enabled": s.enabled,
            "interval_seconds": s.interval_seconds,
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        } for s in rows]

    async def overview(self) -> dict[str, Any]:
        workers, store_ok = await self.list_workers()
        return {
            "workers": workers,
            "worker_heartbeat_store": "available" if store_ok else "unavailable",
            "active_workers": sum(1 for w in workers if w["alive"]),
            "queue_depth": await self.queue_depth(),
            "jobs": self.job_counts(),
            "outbox": self.outbox_counts(),
            "expired_leases": self.expired_leases(),
            "retries": self.retry_activity(),
            "schedules": self.schedule_summary(),
        }
