"""Job handler registry for the Phase 8 worker engine.

Handlers are async callables ``handler(payload: dict, ctx: JobContext)``.
An optional pydantic ``payload_model`` validates the payload before
execution; validation failures are permanent (non-retryable).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session


class PermanentJobError(Exception):
    """Failure that must never be retried (validation, authorization, etc.)."""


@dataclass
class JobContext:
    job_id: str
    project_id: str
    job_type: str
    attempt: int
    session: Session


Handler = Callable[[dict[str, Any], JobContext], Awaitable[Any]]

_REGISTRY: dict[str, tuple[Handler, Optional[type[BaseModel]]]] = {}


def register_handler(
    job_type: str,
    handler: Handler,
    payload_model: Optional[type[BaseModel]] = None,
) -> None:
    _REGISTRY[job_type] = (handler, payload_model)


def get_handler(job_type: str):
    return _REGISTRY.get(job_type)


def registered_types() -> list[str]:
    return sorted(_REGISTRY)


def validate_payload(
    job_type: str, payload: dict[str, Any] | None
) -> dict[str, Any]:
    """Validate payload against the registered model. Returns validated dict."""
    entry = _REGISTRY.get(job_type)
    model = entry[1] if entry else None
    if model is None:
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise PermanentJobError("Job payload must be a JSON object")
        return payload
    try:
        return model.model_validate(payload or {}).model_dump()
    except ValidationError as exc:
        raise PermanentJobError(f"Invalid payload for '{job_type}': {exc}") from exc
