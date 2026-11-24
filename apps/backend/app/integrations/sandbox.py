"""Sandbox adapter — the built-in reference adapter for Phase 6.

Performs zero outbound I/O. It deterministically "executes" an action by
echoing a verified result so the full approval → dispatch → audit pipeline can
be exercised end-to-end without touching any external service.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from app.integrations.base import ExecutionRequest, ExecutionResult


class SandboxAdapter:
    adapter_type = "sandbox"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started = time.monotonic()
        # Deterministic verification payload: proves the exact approved payload
        # reached the adapter without performing any external side effect.
        digest = hashlib.sha256(
            f"{request.action_id}:{request.action_type}:{sorted(request.payload.items())}".encode()
        ).hexdigest()[:16]
        latency_ms = int((time.monotonic() - started) * 1000)
        return ExecutionResult(
            success=True,
            response_status=200,
            latency_ms=latency_ms,
            result={
                "adapter": "sandbox",
                "mode": request.mode,
                "action_type": request.action_type,
                "payload_digest": digest,
                "echo": request.payload,
            },
        )
