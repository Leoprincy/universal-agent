"""Adapter registry — maps provider ``adapter_type`` to adapter instances.

Only sandbox adapters are registered in Phase 6. Real provider adapters are
added here later without touching the orchestration service.
"""

from __future__ import annotations

from app.integrations.base import IntegrationAdapter
from app.integrations.sandbox import SandboxAdapter

_ADAPTERS: dict[str, IntegrationAdapter] = {
    "sandbox": SandboxAdapter(),
}


def get_adapter(adapter_type: str) -> IntegrationAdapter:
    adapter = _ADAPTERS.get(adapter_type)
    if adapter is None:
        raise KeyError(f"No adapter registered for type '{adapter_type}'")
    return adapter


def registered_adapter_types() -> list[str]:
    return sorted(_ADAPTERS)
