"""Phase 8 scheduler.

Two responsibilities, both driven by PostgreSQL state so they survive
restarts:

1. Reconciliation — promote due `pending` jobs to `queued` with an outbox
   dispatch row (covers missed/crashed dispatch).
2. Recurring schedules — materialize each due `job_schedules` occurrence as
   a Job whose idempotency_key encodes the schedule slot, making duplicate
   occurrences impossible even across restarts. Missed occurrences are
   skipped: next_run_at advances to the first future slot.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.models import Job, JobSchedule
from app.services.job import JobService
from app.jobs.queue import UnavailableJobQueue

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def next_slot_after(schedule: JobSchedule, now: datetime) -> datetime:
    """First occurrence strictly after `now`, skipping missed slots."""
    nxt = _aware(schedule.next_run_at)
    interval = timedelta(seconds=schedule.interval_seconds)
    while nxt <= now:
        nxt += interval
    return nxt


async def scheduler_tick(session_factory: sessionmaker) -> dict[str, int]:
    session = session_factory()
    promoted = 0
    materialized = 0
    try:
        service = JobService(session, UnavailableJobQueue())
        promoted = service.promote_due_pending()

        now = _utcnow()
        schedules = session.scalars(
            select(JobSchedule)
            .where(JobSchedule.enabled.is_(True))
            .where(JobSchedule.next_run_at <= now)
            .with_for_update(skip_locked=True)
        ).all()
        for schedule in schedules:
            slot = _aware(schedule.next_run_at)
            idem = f"schedule:{schedule.id}:{slot.isoformat()}"
            existing = session.scalar(
                select(Job.id).where(
                    (Job.project_id == schedule.project_id)
                    & (Job.idempotency_key == idem)
                )
            )
            if existing is None:
                try:
                    with session.begin_nested():
                        job = Job(
                            id=str(uuid.uuid4()),
                            project_id=schedule.project_id,
                            job_type=schedule.job_type,
                            payload_json=schedule.payload_json,
                            status="pending",
                            scheduled_at=slot,
                            idempotency_key=idem,
                            created_by=schedule.created_by,
                        )
                        session.add(job)
                        session.flush()
                        service._queue_job(job, "scheduler", "queued")
                    materialized += 1
                except IntegrityError:
                    # concurrent materialization of the same slot — skip
                    continue
            schedule.last_run_at = slot
            schedule.next_run_at = next_slot_after(schedule, now)
            schedule.updated_at = now
        session.commit()
        return {"promoted": promoted, "materialized": materialized}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
