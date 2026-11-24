"""Deterministic experiment evaluation engine (Phase 7, Milestone 2).

Pure functions — no database, no I/O, no LLM. Compares observed outcomes
against an experiment's predefined success criteria and returns a verdict
with structured, auditable rationale.

Verdict rules (conservative by design):
- ``succeeded``  — every criterion is satisfied by observed data.
- ``failed``     — at least one criterion is definitively not met.
- ``inconclusive`` — otherwise: missing outcomes, insufficient sample size,
  or an incomplete observation window. Insufficient evidence is NEVER
  reported as success.

Correlation is not causation: rationale always states that the verdict only
indicates whether predefined criteria were met by observed measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

COMPARATORS = {
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
}

COMPARATOR_LABELS = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


@dataclass(frozen=True)
class CriterionResult:
    metric_name: str
    comparator: str
    threshold: float
    status: str  # "pass" | "fail" | "inconclusive"
    observed_value: float | None
    sample_size: int | None
    reason: str


@dataclass(frozen=True)
class EvaluationOutcome:
    verdict: str  # "succeeded" | "failed" | "inconclusive"
    criteria: list[CriterionResult] = field(default_factory=list)
    rationale: dict[str, Any] = field(default_factory=dict)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _criterion_window(
    started_at: datetime | None,
    ends_at: datetime | None,
    window_days: int | None,
    now: datetime,
) -> tuple[datetime | None, datetime | None, str | None]:
    """Return (window_start, window_end, incomplete_reason)."""
    if started_at is None:
        return None, None, "experiment has no started_at; cannot bound observation window"
    start = _aware(started_at)
    end = _aware(ends_at) if ends_at else None
    if window_days is not None:
        criterion_end = start + timedelta(days=window_days)
        end = min(end, criterion_end) if end else criterion_end
    if end is not None and _aware(now) < end:
        return start, end, f"observation window incomplete (ends {end.isoformat()})"
    return start, end, None


def _latest_in_window(
    outcomes: Iterable[Any], metric_name: str, start: datetime | None, end: datetime | None
) -> Any | None:
    """Return the latest outcome for a metric inside the window, or None."""
    candidates = []
    for o in outcomes:
        if o.metric_name != metric_name:
            continue
        observed = _aware(o.observed_at)
        if start is not None and observed < start:
            continue
        if end is not None and observed > end:
            continue
        candidates.append(o)
    if not candidates:
        return None
    return max(candidates, key=lambda o: _aware(o.observed_at))


def evaluate_experiment(
    criteria: list[dict[str, Any]],
    outcomes: Iterable[Any],
    started_at: datetime | None,
    ends_at: datetime | None,
    now: datetime | None = None,
) -> EvaluationOutcome:
    """Evaluate observed outcomes against success criteria.

    ``criteria`` items: metric_name, comparator, threshold,
    optional min_sample_size, optional window_days.
    ``outcomes`` items need: metric_name, value, sample_size, observed_at,
    and must already exclude superseded records.
    """
    now = _aware(now or datetime.now(timezone.utc))
    results: list[CriterionResult] = []

    if not criteria:
        return EvaluationOutcome(
            verdict="inconclusive",
            rationale={
                "reason": "no success criteria defined",
                "note": "verdict reflects criterion satisfaction only, not causation",
            },
        )

    any_fail = False
    any_inconclusive = False

    for c in criteria:
        metric = c["metric_name"]
        comparator = c["comparator"]
        threshold = float(c["threshold"])
        min_sample = c.get("min_sample_size")
        window_days = c.get("window_days")

        start, end, window_reason = _criterion_window(
            started_at, ends_at, window_days, now
        )
        if window_reason:
            results.append(
                CriterionResult(metric, comparator, threshold, "inconclusive", None, None, window_reason)
            )
            any_inconclusive = True
            continue

        latest = _latest_in_window(outcomes, metric, start, end)
        if latest is None:
            results.append(
                CriterionResult(
                    metric, comparator, threshold, "inconclusive", None, None,
                    "no observed outcome for this metric in the evaluation window",
                )
            )
            any_inconclusive = True
            continue

        value = float(latest.value)
        sample = latest.sample_size

        if min_sample is not None and (sample is None or sample < min_sample):
            results.append(
                CriterionResult(
                    metric, comparator, threshold, "inconclusive", value, sample,
                    f"insufficient sample size ({sample} < required {min_sample})",
                )
            )
            any_inconclusive = True
            continue

        passed = COMPARATORS[comparator](value, threshold)
        status = "pass" if passed else "fail"
        reason = (
            f"observed {value} {COMPARATOR_LABELS[comparator]} {threshold}"
            + (f" (sample={sample})" if sample is not None else "")
        )
        results.append(CriterionResult(metric, comparator, threshold, status, value, sample, reason))
        if not passed:
            any_fail = True

    if any_fail:
        verdict = "failed"
    elif any_inconclusive:
        verdict = "inconclusive"
    else:
        verdict = "succeeded"

    rationale = {
        "criteria": [
            {
                "metric_name": r.metric_name,
                "comparator": r.comparator,
                "threshold": r.threshold,
                "status": r.status,
                "observed_value": r.observed_value,
                "sample_size": r.sample_size,
                "reason": r.reason,
            }
            for r in results
        ],
        "window": {
            "started_at": started_at.isoformat() if started_at else None,
            "ends_at": ends_at.isoformat() if ends_at else None,
            "evaluated_at": now.isoformat(),
        },
        "note": (
            "Verdict indicates whether predefined success criteria were met by "
            "observed measurements. It does not establish causation."
        ),
    }
    return EvaluationOutcome(verdict=verdict, criteria=results, rationale=rationale)
