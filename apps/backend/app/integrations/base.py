"""Adapter contracts for outbound provider integrations.

Adapters are replaceable: business logic depends only on the
``IntegrationAdapter`` protocol and the ``ExecutionRequest``/``ExecutionResult``
contracts, never on a specific provider, browser, or transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ExecutionRequest:
    """Validated, immutable input handed to an adapter for one attempt."""

    action_id: str
    action_type: str
    payload: dict[str, Any]
    mode: str  # "sandbox" or "live" — resolved by the service, never the adapter
    credentials: dict[str, str] | None = None
    provider_config: dict[str, Any] | None = field(default=None)


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a single adapter attempt."""

    success: bool
    response_status: int | None = None
    latency_ms: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class IntegrationAdapter(Protocol):
    """Replaceable provider adapter.

    ``execute`` must be side-effect free in ``sandbox`` mode: sandbox-only
    providers can never reach this method with ``mode="live"`` because the
    service enforces the mode centrally before dispatch.
    """

    adapter_type: str

    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
