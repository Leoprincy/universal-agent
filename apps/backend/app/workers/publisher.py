"""Transactional outbox publisher.

Drains pending `job_outbox_events` to the queue. Runs inside the worker
process; safe under multiple workers (duplicate queue entries are harmless
because job claims are atomic). At-least-once delivery.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.models import JobOutboxEvent
from app.jobs.queue import JobQueue, QueueUnavailableError

logger = logging.getLogger(__name__)

MAX_OUTBOX_ATTEMPTS = 25


async def publish_pending(
    session_factory: sessionmaker, queue: JobQueue, limit: int = 100
) -> int:
    """Publish up to `limit` pending outbox rows. Returns published count."""
    session = session_factory()
    published = 0
    try:
        rows = session.scalars(
            select(JobOutboxEvent)
            .where(JobOutboxEvent.status == "pending")
            .order_by(JobOutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.attempts += 1
            try:
                await queue.push(row.job_id)
            except QueueUnavailableError as exc:
                row.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if row.attempts >= MAX_OUTBOX_ATTEMPTS:
                    row.status = "failed"
                continue
            row.status = "published"
            row.published_at = datetime.now(timezone.utc)
            published += 1
        if rows:
            session.commit()
        return published
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
