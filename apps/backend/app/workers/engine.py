"""Phase 8 worker engine.

Claims queued jobs with SELECT ... FOR UPDATE, executes registered async
handlers under a timeout, applies retry/backoff policy, and recovers
abandoned leases. At-least-once delivery: handlers performing external side
effects MUST be idempotent — a crash after side effects but before commit
can re-run the handler.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Job, JobEvent
from app.jobs.queue import JobQueue, QueueUnavailableError
from app.workers.handlers import (
    JobContext,
    PermanentJobError,
    get_handler,
    validate_payload,
)

logger = logging.getLogger(__name__)

LEASE_SECONDS = 120
DEFAULT_JOB_TIMEOUT = 300
BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def backoff_seconds(attempt: int, base: int = BASE_BACKOFF_SECONDS,
                    cap: int = MAX_BACKOFF_SECONDS) -> int:
    return min(cap, base * (2 ** max(0, attempt - 1)))


class WorkerEngine:
    def __init__(
        self,
        session_factory: sessionmaker,
        queue: JobQueue,
        worker_id: str | None = None,
        concurrency: int = 2,
        job_timeout: int = DEFAULT_JOB_TIMEOUT,
        lease_seconds: int = LEASE_SECONDS,
        poll_interval: float = 2.0,
        publisher: Optional[Callable[[], Any]] = None,
        scheduler: Optional[Callable[[], Any]] = None,
        heartbeat: Optional[Callable[[], Any]] = None,
        recovery_interval: float = 30.0,
    ) -> None:
        self._sf = session_factory
        self._queue = queue
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.concurrency = concurrency
        self.job_timeout = job_timeout
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval
        self._publisher = publisher
        self._scheduler = scheduler
        self._heartbeat_cb = heartbeat
        self.recovery_interval = recovery_interval
        self._stop = asyncio.Event()
        self.jobs_completed = 0
        self.jobs_failed = 0

    # ── claiming ──────────────────────────────────────────────────────────

    def _claim(self, job_id: str) -> tuple[Job, dict] | None:
        """Atomically claim a queued job for this worker. Returns None if
        the job is not claimable (duplicate message, wrong state, leased)."""
        session = self._sf()
        try:
            job = session.scalar(
                select(Job)
                .where(Job.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job is None or job.status != "queued":
                return None
            if job.scheduled_at is not None and _aware(job.scheduled_at) > _utcnow():
                return None
            if job.locked_until is not None and _aware(job.locked_until) > _utcnow():
                return None
            now = _utcnow()
            job.status = "running"
            job.started_at = job.started_at or now
            job.attempt_count += 1
            job.locked_by = self.worker_id
            job.locked_until = now + timedelta(seconds=self.lease_seconds)
            job.updated_at = now
            self._event(session, job, "started", "queued", "running",
                        self.worker_id,
                        f"claimed by {self.worker_id} (attempt {job.attempt_count})")
            session.commit()
            claimed = {
                "id": job.id, "project_id": job.project_id,
                "job_type": job.job_type, "payload": job.payload_json,
                "attempt": job.attempt_count, "max_attempts": job.max_attempts,
            }
            session.expunge(job)
            return job, claimed
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _event(self, session: Session, job: Job, etype: str,
               frm: str | None, to: str, actor: str,
               message: str | None = None) -> None:
        nxt = (session.scalar(
            select(func.coalesce(func.max(JobEvent.seq), 0))
            .where(JobEvent.job_id == job.id)
        ) or 0) + 1
        session.add(JobEvent(
            id=str(uuid.uuid4()), job_id=job.id, project_id=job.project_id,
            seq=nxt, event_type=etype, from_status=frm, to_status=to,
            message=message, actor=actor,
        ))

    # ── execution ─────────────────────────────────────────────────────────

    async def _heartbeat(self, job_id: str, stop: asyncio.Event) -> None:
        interval = max(5.0, self.lease_seconds / 3)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                pass
            session = self._sf()
            try:
                job = session.scalar(select(Job).where(Job.id == job_id))
                if (job and job.status == "running"
                        and job.locked_by == self.worker_id):
                    job.locked_until = _utcnow() + timedelta(seconds=self.lease_seconds)
                    session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()

    async def _finish(self, job_id: str, target: str, error: str | None = None,
                      retry_at: datetime | None = None) -> None:
        session = self._sf()
        try:
            job = session.scalar(
                select(Job).where(Job.id == job_id).with_for_update()
            )
            if (job is None or job.status != "running"
                    or job.locked_by != self.worker_id):
                return
            now = _utcnow()
            if retry_at is not None:
                # retryable failure → back to pending with backoff schedule
                job.status = "pending"
                job.scheduled_at = retry_at
                job.last_error = (error or "unknown")[:4000]
                job.completed_at = None
                job.locked_by = None
                job.locked_until = None
                self._event(session, job, "failed", "running", "pending",
                            self.worker_id, error)
            elif target == "completed":
                job.status = "completed"
                job.completed_at = now
                job.locked_by = None
                job.locked_until = None
                self._event(session, job, "completed", "running", "completed",
                            self.worker_id, error)
            else:  # terminal failure
                job.status = "failed"
                job.completed_at = now
                job.last_error = (error or "unknown")[:4000]
                job.locked_by = None
                job.locked_until = None
                self._event(session, job, "failed", "running", "failed",
                            self.worker_id, error)
            job.updated_at = now
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def _retry_or_fail(self, claimed: dict, job_id: str, error: str) -> None:
        attempt = claimed["attempt"]
        max_attempts = claimed["max_attempts"]
        if attempt >= max_attempts:
            await self._finish(job_id, "failed", error)
        else:
            delay = backoff_seconds(attempt)
            await self._finish(
                job_id, "failed", error,
                retry_at=_utcnow() + timedelta(seconds=delay),
            )

    async def _execute(self, job_id: str) -> None:
        claimed_pair = self._claim(job_id)
        if claimed_pair is None:
            return  # stale/duplicate/already claimed
        job, claimed = claimed_pair
        hb_stop = asyncio.Event()
        hb = asyncio.create_task(self._heartbeat(job.id, hb_stop))
        try:
            session = self._sf()
            try:
                entry = get_handler(claimed["job_type"])
                if entry is None:
                    raise PermanentJobError(
                        f"No handler registered for job_type '{claimed['job_type']}'"
                    )
                handler, _model = entry
                ctx = JobContext(
                    job_id=job.id, project_id=claimed["project_id"],
                    job_type=claimed["job_type"], attempt=claimed["attempt"],
                    session=session,
                )
                try:
                    payload = validate_payload(
                        claimed["job_type"], claimed["payload"]
                    )
                except PermanentJobError:
                    session.close()
                    raise
                await asyncio.wait_for(
                    handler(payload, ctx), timeout=self.job_timeout
                )
                session.commit()
            except PermanentJobError as exc:
                session.rollback()
                await self._finish(job.id, "failed", str(exc))
                self.jobs_failed += 1
                return
            except asyncio.TimeoutError:
                session.rollback()
                await self._retry_or_fail(claimed, job.id, f"job timed out after {self.job_timeout}s")
                self.jobs_failed += 1
                return
            except Exception as exc:
                session.rollback()
                await self._retry_or_fail(claimed, job.id, f"{type(exc).__name__}: {exc}")
                self.jobs_failed += 1
                return
            finally:
                session.close()
            await self._finish(job.id, "completed")
            self.jobs_completed += 1
        finally:
            hb_stop.set()
            hb.cancel()
            try:
                await hb
            except BaseException:
                pass

    # ── recovery ──────────────────────────────────────────────────────────

    def recover_abandoned(self) -> int:
        """Reset expired running leases. Never marks jobs completed."""
        session = self._sf()
        try:
            now = _utcnow()
            jobs = session.scalars(
                select(Job).where(
                    (Job.status == "running")
                    & (Job.locked_until.isnot(None))
                    & (Job.locked_until < now)
                )
            ).all()
            count = 0
            for job in jobs:
                if job.attempt_count >= job.max_attempts:
                    job.status = "failed"
                    job.completed_at = now
                    job.last_error = ((job.last_error or "") + " | lease expired")[:4000]
                    self._event(session, job, "failed", "running", "failed",
                                "recovery", "worker lease expired; attempts exhausted")
                else:
                    job.status = "pending"
                    job.scheduled_at = now
                    job.locked_by = None
                    job.locked_until = None
                    self._event(session, job, "failed", "running", "pending",
                                "recovery", "worker lease expired; requeued")
                count += 1
            if count:
                session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ── main loop ─────────────────────────────────────────────────────────

    async def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = await self._queue.pop(timeout=self.poll_interval)
            except Exception:
                await asyncio.sleep(self.poll_interval)
                continue
            if item is None:
                continue
            try:
                await self._execute(item)
            except Exception:
                logger.exception("Worker failed to execute job %s", item)

    async def _maintenance_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.recovery_interval
                )
                return
            except asyncio.TimeoutError:
                pass
            try:
                self.recover_abandoned()
                if self._publisher:
                    res = self._publisher()
                    if asyncio.iscoroutine(res):
                        await res
                if self._scheduler:
                    res = self._scheduler()
                    if asyncio.iscoroutine(res):
                        await res
                if self._heartbeat_cb:
                    res = self._heartbeat_cb()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception:
                logger.exception("Worker maintenance tick failed")

    async def run(self) -> None:
        logger.info("Worker %s starting (concurrency=%d)",
                    self.worker_id, self.concurrency)
        tasks = [asyncio.create_task(self._worker_loop())
                 for _ in range(self.concurrency)]
        tasks.append(asyncio.create_task(self._maintenance_loop()))
        try:
            await self._stop.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Worker %s stopped", self.worker_id)

    def stop(self) -> None:
        self._stop.set()
