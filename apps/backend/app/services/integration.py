"""Phase 6 integration provider and action orchestration service.

Owns the approval-gated lifecycle for outbound provider actions:

    pending_approval → approved → executing → succeeded | failed
                    ↘ rejected | expired | cancelled

Safety invariants enforced here (single place, no bypasses):
- sandbox_only providers can never dispatch in live mode;
- approval is bound to the immutable payload hash and expires after the
  configured TTL (separate pending-approval and post-approval windows);
- rate limits are enforced under a provider row lock so they hold across
  workers and restarts;
- action rows are locked during execution so an action can never run twice;
- every decision and attempt is appended to immutable event/call-log tables.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ApplicationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    UnprocessableEntityError,
)
from app.database.models import (
    IntegrationAction,
    IntegrationActionEvent,
    IntegrationCallLog,
    IntegrationCredential,
    IntegrationProvider,
)
from app.integrations.base import ExecutionRequest
from app.integrations.codec import CredentialCodec, CredentialConfigError
from app.integrations.registry import get_adapter, registered_adapter_types
from app.schemas.integration import (
    IntegrationActionCreate,
    IntegrationProviderCreate,
    IntegrationProviderUpdate,
)

ACTION_STATUSES = {
    "pending_approval",
    "approved",
    "rejected",
    "expired",
    "executing",
    "succeeded",
    "failed",
    "cancelled",
}

DECIDABLE_STATUSES = {"pending_approval"}
CANCELLABLE_STATUSES = {"pending_approval", "approved"}
RATE_LIMIT_WINDOW_SECONDS = 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Normalize DB-returned naive datetimes to UTC-aware for comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IntegrationService:
    def __init__(
        self,
        session: Session,
        credential_codec: CredentialCodec | None = None,
        approval_ttl_seconds: int = 86400,
    ) -> None:
        self._session = session
        self._codec = credential_codec
        self._approval_ttl = timedelta(seconds=approval_ttl_seconds)

    # ── providers ──────────────────────────────────────────────────────────

    def create_provider(
        self, data: IntegrationProviderCreate, project_id: str
    ) -> IntegrationProvider:
        if data.adapter_type not in registered_adapter_types():
            raise UnprocessableEntityError(
                f"Unknown adapter_type '{data.adapter_type}'. Registered: {registered_adapter_types()}",
                code="unknown_adapter_type",
            )
        provider = IntegrationProvider(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=data.name.strip(),
            adapter_type=data.adapter_type,
            enabled=data.enabled,
            sandbox_only=data.sandbox_only,
            rate_limit_per_minute=data.rate_limit_per_minute,
            config_json=data.config,
        )
        self._session.add(provider)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"A provider named '{data.name}' already exists in this project",
                code="duplicate_provider_name",
            ) from exc
        self._session.refresh(provider)
        return provider

    def list_providers(self, project_id: str) -> Sequence[IntegrationProvider]:
        return self._session.scalars(
            select(IntegrationProvider)
            .where(IntegrationProvider.project_id == project_id)
            .order_by(IntegrationProvider.created_at)
        ).all()

    def get_provider(
        self, provider_id_or_name: str, project_id: str
    ) -> IntegrationProvider:
        stmt = select(IntegrationProvider).where(
            IntegrationProvider.project_id == project_id
        )
        provider = self._session.scalar(
            stmt.where(
                (IntegrationProvider.id == provider_id_or_name)
                | (IntegrationProvider.name == provider_id_or_name)
            )
        )
        if provider is None:
            raise NotFoundError(f"Integration provider '{provider_id_or_name}' not found")
        return provider

    def update_provider(
        self,
        provider_id_or_name: str,
        data: IntegrationProviderUpdate,
        project_id: str,
    ) -> IntegrationProvider:
        provider = self.get_provider(provider_id_or_name, project_id)
        for field in ("enabled", "sandbox_only", "rate_limit_per_minute", "config_json"):
            value = getattr(data, "config" if field == "config_json" else field)
            if value is not None:
                setattr(provider, field, value)
        provider.updated_at = _utcnow()
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Provider update violates a uniqueness constraint", code="conflict"
            ) from exc
        self._session.refresh(provider)
        return provider

    def delete_provider(
        self, provider_id_or_name: str, project_id: str
    ) -> None:
        provider = self.get_provider(provider_id_or_name, project_id)
        linked = self._session.scalar(
            select(func.count())
            .select_from(IntegrationAction)
            .where(
                (IntegrationAction.provider_id == provider.id)
                & (IntegrationAction.project_id == project_id)
            )
        )
        if linked:
            raise ConflictError(
                "Provider cannot be deleted because it has integration actions. "
                "Disable it instead to preserve the audit trail.",
                code="provider_has_actions",
            )
        try:
            self._session.delete(provider)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Provider cannot be deleted while credentials or audit records reference it",
                code="provider_in_use",
            ) from exc

    # ── credentials (write-only) ───────────────────────────────────────────

    def set_credential(
        self, provider_id_or_name: str, credential: str, project_id: str
    ) -> None:
        if self._codec is None:
            raise ApplicationError(
                "Credential storage is not configured (UGA_CREDENTIAL_ENCRYPTION_KEY)",
                code="credential_store_unavailable",
                status_code=503,
            )
        provider = self.get_provider(provider_id_or_name, project_id)
        try:
            ciphertext = self._codec.encrypt(credential)
        except CredentialConfigError as exc:
            raise ApplicationError(
                "Credential storage is not configured correctly",
                code="credential_store_unavailable",
                status_code=503,
            ) from exc
        row = self._session.scalar(
            select(IntegrationCredential).where(
                (IntegrationCredential.provider_id == provider.id)
                & (IntegrationCredential.project_id == project_id)
            )
        )
        if row is None:
            row = IntegrationCredential(
                id=str(uuid.uuid4()),
                provider_id=provider.id,
                project_id=project_id,
                ciphertext=ciphertext,
                key_version=self._codec.KEY_VERSION,
            )
            self._session.add(row)
        else:
            row.ciphertext = ciphertext
            row.key_version = self._codec.KEY_VERSION
            row.updated_at = _utcnow()
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Credential could not be stored", code="conflict"
            ) from exc

    def has_credential(self, provider_id: str, project_id: str) -> bool:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(IntegrationCredential)
                .where(
                    (IntegrationCredential.provider_id == provider_id)
                    & (IntegrationCredential.project_id == project_id)
                )
            )
            or 0
        ) > 0

    def _decrypt_credentials(
        self, provider: IntegrationProvider, project_id: str
    ) -> dict[str, str] | None:
        row = self._session.scalar(
            select(IntegrationCredential).where(
                (IntegrationCredential.provider_id == provider.id)
                & (IntegrationCredential.project_id == project_id)
            )
        )
        if row is None or self._codec is None:
            return None
        try:
            plaintext = self._codec.decrypt(row.ciphertext)
            parsed = json.loads(plaintext)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (CredentialConfigError, json.JSONDecodeError):
            return None

    # ── actions: creation & listing ────────────────────────────────────────

    def create_action(
        self,
        provider_id_or_name: str,
        data: IntegrationActionCreate,
        project_id: str,
        actor: str,
    ) -> tuple[IntegrationAction, bool]:
        """Create an action in ``pending_approval``.

        Returns ``(action, created)``; ``created`` is False when an existing
        action with the same idempotency key is returned instead.
        """
        provider = self.get_provider(provider_id_or_name, project_id)
        if not provider.enabled:
            raise ConflictError(
                f"Provider '{provider.name}' is disabled", code="provider_disabled"
            )
        if data.idempotency_key:
            existing = self._session.scalar(
                select(IntegrationAction).where(
                    (IntegrationAction.provider_id == provider.id)
                    & (IntegrationAction.idempotency_key == data.idempotency_key)
                )
            )
            if existing is not None:
                return existing, False

        now = _utcnow()
        action = IntegrationAction(
            id=str(uuid.uuid4()),
            project_id=project_id,
            provider_id=provider.id,
            action_type=data.action_type.strip(),
            payload_json=data.payload,
            payload_hash=_payload_hash(data.payload),
            status="pending_approval",
            idempotency_key=data.idempotency_key,
            actor=actor,
            pending_approval_expires_at=now + self._approval_ttl,
            attempt_count=0,
        )
        self._session.add(action)
        self._record_event(action, "submitted", actor, {"action_type": action.action_type})
        try:
            self._session.flush()
            self._session.commit()
        except IntegrityError:
            # Concurrent create with the same idempotency key: the winning
            # transaction may not be visible yet, so retry briefly before
            # giving up and returning the existing action.
            self._session.rollback()
            if data.idempotency_key:
                import time

                for _ in range(40):
                    existing = self._session.scalar(
                        select(IntegrationAction).where(
                            (IntegrationAction.provider_id == provider.id)
                            & (IntegrationAction.idempotency_key == data.idempotency_key)
                        )
                    )
                    if existing is not None:
                        return existing, False
                    time.sleep(0.05)
            raise
        self._session.refresh(action)
        return action, True

    def list_actions(
        self,
        project_id: str,
        provider_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[IntegrationAction], int]:
        base = select(IntegrationAction).where(
            IntegrationAction.project_id == project_id
        )
        count_q = (
            select(func.count())
            .select_from(IntegrationAction)
            .where(IntegrationAction.project_id == project_id)
        )
        if provider_id:
            provider = self.get_provider(provider_id, project_id)
            base = base.where(IntegrationAction.provider_id == provider.id)
            count_q = count_q.where(IntegrationAction.provider_id == provider.id)
        if status:
            if status not in ACTION_STATUSES:
                raise UnprocessableEntityError(
                    f"Invalid status '{status}'", code="invalid_status_filter"
                )
            base = base.where(IntegrationAction.status == status)
            count_q = count_q.where(IntegrationAction.status == status)
        total = self._session.scalar(count_q) or 0
        items = self._session.scalars(
            base.order_by(IntegrationAction.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return items, total

    def get_action(
        self, action_id_or_slug: str, project_id: str, for_update: bool = False
    ) -> IntegrationAction:
        stmt = (
            select(IntegrationAction)
            .where(
                (IntegrationAction.project_id == project_id)
                & (IntegrationAction.id == action_id_or_slug)
            )
            .with_for_update()
            if for_update
            else select(IntegrationAction).where(
                (IntegrationAction.project_id == project_id)
                & (IntegrationAction.id == action_id_or_slug)
            )
        )
        action = self._session.scalar(stmt)
        if action is None:
            raise NotFoundError(f"Integration action '{action_id_or_slug}' not found")
        return action

    # ── actions: decisions ─────────────────────────────────────────────────

    def _expire_pending_if_needed(self, action: IntegrationAction) -> bool:
        expires = _aware(action.pending_approval_expires_at)
        if action.status == "pending_approval" and expires and _utcnow() > expires:
            action.status = "expired"
            action.updated_at = _utcnow()
            self._record_event(action, "expired", action.actor, {"reason": "pending_approval_ttl_elapsed"})
            return True
        return False

    def approve(
        self, action_id: str, project_id: str, actor: str, reason: str | None
    ) -> IntegrationAction:
        action = self.get_action(action_id, project_id)
        if self._expire_pending_if_needed(action):
            self._session.commit()
            raise ConflictError(
                "Action approval window has expired", code="action_expired"
            )
        if action.status != "pending_approval":
            raise ConflictError(
                f"Action is '{action.status}' and cannot be approved",
                code="invalid_action_state",
            )
        now = _utcnow()
        action.status = "approved"
        action.approver = actor
        action.decision_reason = reason
        action.decided_at = now
        action.approval_expires_at = now + self._approval_ttl
        action.updated_at = now
        self._record_event(action, "approved", actor, {"reason": reason})
        self._session.commit()
        self._session.refresh(action)
        return action

    def reject(
        self, action_id: str, project_id: str, actor: str, reason: str | None
    ) -> IntegrationAction:
        action = self.get_action(action_id, project_id)
        if self._expire_pending_if_needed(action):
            self._session.commit()
            raise ConflictError(
                "Action approval window has expired", code="action_expired"
            )
        if action.status != "pending_approval":
            raise ConflictError(
                f"Action is '{action.status}' and cannot be rejected",
                code="invalid_action_state",
            )
        now = _utcnow()
        action.status = "rejected"
        action.approver = actor
        action.decision_reason = reason
        action.decided_at = now
        action.updated_at = now
        self._record_event(action, "rejected", actor, {"reason": reason})
        self._session.commit()
        self._session.refresh(action)
        return action

    def cancel(
        self, action_id: str, project_id: str, actor: str, reason: str | None
    ) -> IntegrationAction:
        action = self.get_action(action_id, project_id)
        expired = False
        if action.status == "pending_approval":
            expired = self._expire_pending_if_needed(action)
        if expired or action.status not in CANCELLABLE_STATUSES:
            if expired:
                self._session.commit()
            raise ConflictError(
                f"Action is '{action.status}' and cannot be cancelled",
                code="invalid_action_state",
            )
        now = _utcnow()
        action.status = "cancelled"
        action.approver = actor
        action.decision_reason = reason
        action.decided_at = now
        action.updated_at = now
        self._record_event(action, "cancelled", actor, {"reason": reason})
        self._session.commit()
        self._session.refresh(action)
        return action

    # ── actions: execution ─────────────────────────────────────────────────

    def execute(
        self, action_id: str, project_id: str, actor: str
    ) -> IntegrationAction:
        """Dispatch an approved action exactly once.

        Locks the action row and the provider row so concurrent workers cannot
        double-execute or bypass the shared rate limit.
        """
        action = self.get_action(action_id, project_id, for_update=True)

        approval_expiry = _aware(action.approval_expires_at)
        if (
            action.status == "approved"
            and approval_expiry is not None
            and _utcnow() > approval_expiry
        ):
            action.status = "expired"
            action.updated_at = _utcnow()
            self._record_event(action, "expired", actor, {"reason": "approval_ttl_elapsed"})
            self._session.commit()
            raise ConflictError(
                "Action approval has expired and can no longer execute",
                code="action_expired",
            )

        if action.status != "approved":
            raise ConflictError(
                f"Action is '{action.status}' and cannot be executed",
                code="invalid_action_state",
            )

        provider = self._session.scalar(
            select(IntegrationProvider)
            .where(
                (IntegrationProvider.id == action.provider_id)
                & (IntegrationProvider.project_id == project_id)
            )
            .with_for_update()
        )
        if provider is None:
            raise NotFoundError("Linked integration provider not found")
        if not provider.enabled:
            raise ConflictError(
                f"Provider '{provider.name}' is disabled", code="provider_disabled"
            )

        # Shared rate limit: provider row is locked above, so the count and the
        # dispatch are serialized across all workers.
        window_start = _utcnow() - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        recent_calls = self._session.scalar(
            select(func.count())
            .select_from(IntegrationCallLog)
            .where(
                (IntegrationCallLog.provider_id == provider.id)
                & (IntegrationCallLog.project_id == project_id)
                & (IntegrationCallLog.created_at >= window_start)
            )
        ) or 0
        if recent_calls >= provider.rate_limit_per_minute:
            self._session.rollback()
            raise RateLimitError(
                f"Provider '{provider.name}' rate limit of "
                f"{provider.rate_limit_per_minute} executions/minute exceeded",
                code="rate_limited",
            )

        mode = "sandbox" if provider.sandbox_only else "live"
        try:
            adapter = get_adapter(provider.adapter_type)
        except KeyError as exc:
            raise UnprocessableEntityError(
                f"Provider adapter '{provider.adapter_type}' is not available",
                code="unknown_adapter_type",
            ) from exc

        credentials = self._decrypt_credentials(provider, project_id)
        request = ExecutionRequest(
            action_id=action.id,
            action_type=action.action_type,
            payload=action.payload_json or {},
            mode=mode,
            credentials=credentials,
            provider_config=provider.config_json,
        )

        now = _utcnow()
        action.status = "executing"
        action.attempt_count = (action.attempt_count or 0) + 1
        action.updated_at = now
        self._record_event(
            action, "executing", actor, {"mode": mode, "attempt": action.attempt_count}
        )
        self._session.flush()

        try:
            result = adapter.execute(request)
        except Exception as exc:  # adapter failure is data, not a crash
            result = None
            adapter_error = str(exc)
        else:
            adapter_error = None

        log = IntegrationCallLog(
            id=str(uuid.uuid4()),
            action_id=action.id,
            project_id=project_id,
            provider_id=provider.id,
            attempt=action.attempt_count,
            mode=mode,
            status="succeeded" if (result and result.success) else "failed",
            response_status=result.response_status if result else None,
            latency_ms=result.latency_ms if result else None,
            error=(result.error if result else None) or adapter_error,
        )
        self._session.add(log)

        finished = _utcnow()
        action.executed_at = finished
        action.updated_at = finished
        if result and result.success:
            action.status = "succeeded"
            action.result_json = result.result
            action.error = None
            self._record_event(action, "succeeded", actor, {"mode": mode})
        else:
            action.status = "failed"
            action.result_json = result.result if result else None
            action.error = (result.error if result else None) or adapter_error or "Adapter execution failed"
            self._record_event(
                action, "failed", actor, {"mode": mode, "error": action.error}
            )
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        self._session.refresh(action)
        return action

    # ── audit reads ────────────────────────────────────────────────────────

    def list_events(
        self, action_id: str, project_id: str
    ) -> Sequence[IntegrationActionEvent]:
        self.get_action(action_id, project_id)  # 404 scoping
        return self._session.scalars(
            select(IntegrationActionEvent)
            .where(
                (IntegrationActionEvent.action_id == action_id)
                & (IntegrationActionEvent.project_id == project_id)
            )
            .order_by(IntegrationActionEvent.seq, IntegrationActionEvent.created_at)
        ).all()

    def list_call_logs(
        self, action_id: str, project_id: str
    ) -> Sequence[IntegrationCallLog]:
        self.get_action(action_id, project_id)
        return self._session.scalars(
            select(IntegrationCallLog)
            .where(
                (IntegrationCallLog.action_id == action_id)
                & (IntegrationCallLog.project_id == project_id)
            )
            .order_by(IntegrationCallLog.created_at, IntegrationCallLog.id)
        ).all()

    def _record_event(
        self,
        action: IntegrationAction,
        event_type: str,
        actor: str,
        detail: dict[str, Any] | None,
    ) -> None:
        seq = (
            self._session.scalar(
                select(func.coalesce(func.max(IntegrationActionEvent.seq), 0)).where(
                    (IntegrationActionEvent.action_id == action.id)
                    & (IntegrationActionEvent.project_id == action.project_id)
                )
            )
            or 0
        ) + 1
        self._session.add(
            IntegrationActionEvent(
                id=str(uuid.uuid4()),
                action_id=action.id,
                project_id=action.project_id,
                event_type=event_type,
                actor=actor,
                detail_json=detail,
                seq=seq,
            )
        )
