"""Phase 8 job service: lifecycle, queueing, audit.

PostgreSQL `jobs` is the durable source of truth. `JobQueue` adapters carry
only job ID references; enqueue pushes the ID then commits the status change
inside one transaction guarded by a row lock.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError, ConflictError, NotFoundError
from app.database.models import Job, JobEvent, JobOutboxEvent, JobSchedule
from app.jobs.queue import JobQueue
from app.schemas.job import JobCreate

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"queued", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"completed", "failed"},
    "failed": {"queued"},  # manual requeue; retry orchestration is Milestone 2+
    "completed": set(),
    "cancelled": set(),
}

JOB_TYPE_PATTERN_MAX = 100


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobService:
    def __init__(self, session: Session, queue: JobQueue) -> None:
        self._session = session
        self._queue = queue

    # ── helpers ───────────────────────────────────────────────────────────

    def _resolve_job(self, job_id: str, project_id: str) -> Job:
        job = self._session.scalar(
            select(Job).where((Job.id == job_id) & (Job.project_id == project_id))
        )
        if job is None:
            raise NotFoundError(f"Job '{job_id}' not found")
        return job

    def _lock_job(self, job_id: str, project_id: str) -> Job:
        job = self._session.scalar(
            select(Job)
            .where((Job.id == job_id) & (Job.project_id == project_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job is None:
            raise NotFoundError(f"Job '{job_id}' not found")
        return job

    def _record_event(
        self,
        job: Job,
        event_type: str,
        from_status: str | None,
        to_status: str,
        actor: str,
        message: str | None = None,
    ) -> None:
        next_seq = (
            self._session.scalar(
                select(func.coalesce(func.max(JobEvent.seq), 0)).where(
                    JobEvent.job_id == job.id
                )
            )
            or 0
        ) + 1
        self._session.add(
            JobEvent(
                id=str(uuid.uuid4()),
                job_id=job.id,
                project_id=job.project_id,
                seq=next_seq,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                message=message,
                actor=actor,
            )
        )

    def _apply_transition(
        self,
        job: Job,
        target: str,
        actor: str,
        event_type: str,
        message: str | None = None,
        error: str | None = None,
    ) -> Job:
        current = job.status
        if current == target:
            raise ConflictError(
                f"Job is already '{current}'", code="invalid_job_transition"
            )
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise ConflictError(
                f"Cannot transition job from '{current}' to '{target}'. "
                f"Allowed: {sorted(ALLOWED_TRANSITIONS.get(current, set()))}",
                code="invalid_job_transition",
            )
        job.status = target
        job.updated_at = _utcnow()
        if target == "running":
            job.started_at = job.started_at or _utcnow()
            job.attempt_count += 1
        if target in {"completed", "failed", "cancelled"}:
            job.completed_at = _utcnow()
        if error is not None:
            job.last_error = error[:4000]
        self._record_event(job, event_type, current, target, actor, message)
        return job

    # ── public API ────────────────────────────────────────────────────────

    def create_job(
        self, data: JobCreate, project_id: str, actor: str
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            job_type=data.job_type.strip(),
            payload_json=data.payload,
            status="pending",
            priority=data.priority,
            scheduled_at=data.scheduled_at,
            max_attempts=data.max_attempts,
            idempotency_key=data.idempotency_key,
            correlation_id=data.correlation_id,
            created_by=actor,
        )
        self._session.add(job)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            if data.idempotency_key:
                existing = self._session.scalar(
                    select(Job).where(
                        (Job.project_id == project_id)
                        & (Job.idempotency_key == data.idempotency_key)
                    )
                )
                if existing is not None:
                    return existing
            raise ConflictError(
                "Job could not be created (duplicate or constraint violation)",
                code="job_create_conflict",
            )
        self._record_event(job, "created", None, "pending", actor)
        self._session.commit()
        self._session.refresh(job)
        return job

    def get_job(self, job_id: str, project_id: str) -> Job:
        return self._resolve_job(job_id, project_id)

    def list_jobs(
        self,
        project_id: str,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Job], int]:
        if status is not None and status not in {
            "pending", "queued", "running", "completed", "failed", "cancelled"
        }:
            raise ApplicationError(
                f"Invalid status filter '{status}'",
                code="invalid_status_filter",
                status_code=422,
            )
        base = select(Job).where(Job.project_id == project_id)
        count_q = (
            select(func.count()).select_from(Job).where(Job.project_id == project_id)
        )
        if status:
            base = base.where(Job.status == status)
            count_q = count_q.where(Job.status == status)
        if job_type:
            base = base.where(Job.job_type == job_type)
            count_q = count_q.where(Job.job_type == job_type)
        total = self._session.scalar(count_q) or 0
        items = self._session.scalars(
            base.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return items, total

    def _queue_job(self, job: Job, actor: str, event_type: str) -> None:
        """Transition to queued and write an outbox dispatch row atomically.

        The outbox publisher delivers the job ID to Redis independently;
        PostgreSQL remains the durable source of truth.
        """
        self._apply_transition(job, "queued", actor, event_type)
        self._session.add(
            JobOutboxEvent(
                id=str(uuid.uuid4()),
                job_id=job.id,
                project_id=job.project_id,
                status="pending",
            )
        )

    async def enqueue_job(
        self, job_id: str, project_id: str, actor: str
    ) -> Job:
        """Mark a pending/failed job queued and record a dispatch outbox row."""
        job = self._lock_job(job_id, project_id)
        event_type = "queued" if job.status != "failed" else "requeued"
        if "queued" not in ALLOWED_TRANSITIONS.get(job.status, set()):
            raise ConflictError(
                f"Cannot queue job from status '{job.status}'",
                code="invalid_job_transition",
            )
        self._queue_job(job, actor, event_type)
        self._session.commit()
        self._session.refresh(job)
        return job

    def promote_due_pending(self, limit: int = 100) -> int:
        """Reconciliation: queue pending jobs whose scheduled_at is due.

        Covers jobs whose dispatch outbox was never written (e.g. schedule
        materialization raced a crash). Returns number promoted.
        """
        now = _utcnow()
        jobs = self._session.scalars(
            select(Job)
            .where(
                (Job.status == "pending")
                & ((Job.scheduled_at.is_(None)) | (Job.scheduled_at <= now))
            )
            .order_by(Job.priority.desc(), Job.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            self._queue_job(job, "scheduler", "queued")
        if jobs:
            self._session.commit()
        return len(jobs)

    def queue_eligible_jobs(self, project_id: str | None = None) -> Sequence[Job]:
        """Pending jobs whose scheduled_at is due (or unset). Read-only."""
        now = _utcnow()
        stmt = select(Job).where(
            (Job.status == "pending")
            & ((Job.scheduled_at.is_(None)) | (Job.scheduled_at <= now))
        )
        if project_id:
            stmt = stmt.where(Job.project_id == project_id)
        return self._session.scalars(
            stmt.order_by(Job.priority.desc(), Job.created_at).limit(100)
        ).all()

    def transition_job(
        self,
        job_id: str,
        project_id: str,
        target: str,
        actor: str,
        message: str | None = None,
        error: str | None = None,
    ) -> Job:
        """Generic guarded transition for worker-facing state changes."""
        job = self._lock_job(job_id, project_id)
        event_map = {
            "running": "started",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        self._apply_transition(
            job, target, actor, event_map.get(target, "queued"), message, error
        )
        self._session.commit()
        self._session.refresh(job)
        return job

    def cancel_job(self, job_id: str, project_id: str, actor: str) -> Job:
        job = self._lock_job(job_id, project_id)
        if job.status == "running":
            raise ConflictError(
                "Cannot cancel a running job; wait for it to finish or fail",
                code="job_running",
            )
        self._apply_transition(job, "cancelled", actor, "cancelled")
        self._session.commit()
        self._session.refresh(job)
        return job

    def get_events(self, job_id: str, project_id: str) -> Sequence[JobEvent]:
        self._resolve_job(job_id, project_id)
        return self._session.scalars(
            select(JobEvent)
            .where((JobEvent.job_id == job_id) & (JobEvent.project_id == project_id))
            .order_by(JobEvent.seq)
        ).all()


    def job_stats(self, project_id: str) -> dict[str, int]:
        """Per-project job counts by status plus retry activity."""
        rows = self._session.execute(
            select(Job.status, func.count())
            .where(Job.project_id == project_id)
            .group_by(Job.status)
        ).all()
        counts = {s: 0 for s in
                  ("pending", "queued", "running", "completed", "failed", "cancelled")}
        for status, n in rows:
            counts[status] = n
        retries = self._session.scalar(
            select(func.count()).select_from(Job).where(
                (Job.project_id == project_id) & (Job.attempt_count > 1)
            )
        ) or 0
        counts["with_retries"] = retries
        return counts

class JobScheduleService:
    """Persistent recurring schedule management (Phase 8)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _resolve(self, schedule_id: str, project_id: str) -> JobSchedule:
        schedule = self._session.scalar(
            select(JobSchedule).where(
                (JobSchedule.id == schedule_id)
                & (JobSchedule.project_id == project_id)
            )
        )
        if schedule is None:
            raise NotFoundError(f"Job schedule '{schedule_id}' not found")
        return schedule

    def create_schedule(
        self,
        project_id: str,
        name: str,
        job_type: str,
        payload: dict[str, Any] | None,
        interval_seconds: int,
        next_run_at: datetime,
        actor: str,
    ) -> JobSchedule:
        schedule = JobSchedule(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=name.strip(),
            job_type=job_type.strip(),
            payload_json=payload,
            interval_seconds=interval_seconds,
            next_run_at=next_run_at,
            enabled=True,
            created_by=actor,
        )
        self._session.add(schedule)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                "A schedule with this name already exists for the project",
                code="schedule_conflict",
            )
        self._session.refresh(schedule)
        return schedule

    def list_schedules(self, project_id: str) -> Sequence[JobSchedule]:
        return self._session.scalars(
            select(JobSchedule)
            .where(JobSchedule.project_id == project_id)
            .order_by(JobSchedule.name)
        ).all()

    def set_enabled(
        self, schedule_id: str, project_id: str, enabled: bool, actor: str
    ) -> JobSchedule:
        schedule = self._session.scalar(
            select(JobSchedule)
            .where(
                (JobSchedule.id == schedule_id)
                & (JobSchedule.project_id == project_id)
            )
            .with_for_update()
        )
        if schedule is None:
            raise NotFoundError(f"Job schedule '{schedule_id}' not found")
        schedule.enabled = enabled
        schedule.updated_at = _utcnow()
        self._session.commit()
        self._session.refresh(schedule)
        return schedule
