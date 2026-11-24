"""Phase 7 experiment management, outcomes, and deterministic evaluation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import (
    Experiment,
    ExperimentEvaluation,
    ExperimentOutcome,
    ExperimentStatusHistory,
    StrategyGoal,
)
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentOutcomeCreate,
    ExperimentTransition,
    ExperimentUpdate,
    SuccessCriteria,
)
from app.services.evaluation import evaluate_experiment

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_review", "cancelled"},
    "in_review": {"draft", "running", "cancelled"},
    "running": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

REASON_REQUIRED_TRANSITIONS: set[tuple[str, str]] = {
    ("in_review", "draft"),
    ("running", "cancelled"),
}

EDITABLE_STATUSES = {"draft"}
STARTED_STATUSES = {"running", "completed", "cancelled"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class ExperimentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── resolution helpers ────────────────────────────────────────────────

    def _resolve_strategy(self, strategy_id_or_slug: str, project_id: str):
        from app.database.models import GrowthStrategy

        strategy = self._session.scalar(
            select(GrowthStrategy).where(
                (GrowthStrategy.project_id == project_id)
                & ((GrowthStrategy.id == strategy_id_or_slug) | (GrowthStrategy.slug == strategy_id_or_slug))
            )
        )
        if strategy is None:
            raise NotFoundError(f"Strategy '{strategy_id_or_slug}' not found")
        return strategy

    def _resolve_experiment(
        self, experiment_id: str, strategy_id: str, project_id: str
    ) -> Experiment:
        exp = self._session.scalar(
            select(Experiment).where(
                (Experiment.id == experiment_id)
                & (Experiment.strategy_id == strategy_id)
                & (Experiment.project_id == project_id)
            )
        )
        if exp is None:
            raise NotFoundError(f"Experiment '{experiment_id}' not found")
        return exp

    def _resolve_goal(self, goal_id: str, strategy_id: str, project_id: str) -> StrategyGoal:
        goal = self._session.scalar(
            select(StrategyGoal).where(
                (StrategyGoal.id == goal_id)
                & (StrategyGoal.strategy_id == strategy_id)
                & (StrategyGoal.project_id == project_id)
            )
        )
        if goal is None:
            raise NotFoundError(f"Goal '{goal_id}' not found for this strategy")
        return goal

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create_experiment(
        self,
        strategy_id_or_slug: str,
        data: ExperimentCreate,
        project_id: str,
        actor: str,
    ) -> Experiment:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        if data.ends_at is not None and data.ends_at <= _utcnow():
            raise UnprocessableEntityError(
                "ends_at must be in the future", code="invalid_ends_at"
            )
        goal_id = None
        if data.goal_id:
            goal = self._resolve_goal(data.goal_id, strategy.id, project_id)
            goal_id = goal.id
        exp = Experiment(
            id=str(uuid.uuid4()),
            project_id=project_id,
            strategy_id=strategy.id,
            goal_id=goal_id,
            name=data.name.strip(),
            hypothesis=data.hypothesis,
            success_criteria_json=(
                data.success_criteria.model_dump() if data.success_criteria else None
            ),
            status="draft",
            ends_at=data.ends_at,
        )
        self._session.add(exp)
        self._session.flush()
        self._record_history(exp, None, "draft", actor, None, {})
        self._session.commit()
        self._session.refresh(exp)
        return exp

    def list_experiments(
        self,
        strategy_id_or_slug: str,
        project_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Experiment], int]:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        base = select(Experiment).where(
            (Experiment.strategy_id == strategy.id)
            & (Experiment.project_id == project_id)
        )
        count_q = (
            select(func.count())
            .select_from(Experiment)
            .where(
                (Experiment.strategy_id == strategy.id)
                & (Experiment.project_id == project_id)
            )
        )
        if status:
            if status not in {
                "draft", "in_review", "running", "completed", "cancelled"
            }:
                raise UnprocessableEntityError(
                    f"Invalid status filter '{status}'", code="invalid_status_filter"
                )
            base = base.where(Experiment.status == status)
            count_q = count_q.where(Experiment.status == status)
        total = self._session.scalar(count_q) or 0
        items = self._session.scalars(
            base.order_by(Experiment.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return items, total

    def get_experiment(
        self, experiment_id: str, strategy_id_or_slug: str, project_id: str
    ) -> Experiment:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        return self._resolve_experiment(experiment_id, strategy.id, project_id)

    def update_experiment(
        self,
        experiment_id: str,
        strategy_id_or_slug: str,
        data: ExperimentUpdate,
        project_id: str,
        actor: str,
    ) -> Experiment:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)

        if exp.status not in EDITABLE_STATUSES:
            # After an experiment leaves draft, descriptive fields and criteria
            # are frozen; only lifecycle transitions may change it.
            mutable = {"ends_at"}
            provided = data.model_fields_set - mutable
            if provided:
                raise ConflictError(
                    f"Experiment is '{exp.status}'; fields {sorted(provided)} are immutable after draft. Only ends_at may be adjusted.",
                    code="experiment_fields_immutable",
                )

        if data.name is not None:
            exp.name = data.name.strip()
        if data.hypothesis is not None:
            exp.hypothesis = data.hypothesis
        if "goal_id" in data.model_fields_set:
            if data.goal_id is None:
                exp.goal_id = None
            else:
                exp.goal_id = self._resolve_goal(data.goal_id, strategy.id, project_id).id
        if "success_criteria" in data.model_fields_set:
            exp.success_criteria_json = (
                data.success_criteria.model_dump() if data.success_criteria else None
            )
        if "ends_at" in data.model_fields_set:
            if (
                data.ends_at is not None
                and exp.started_at is not None
                and _aware(data.ends_at) <= _aware(exp.started_at)
            ):
                raise UnprocessableEntityError(
                    "ends_at must be after started_at", code="invalid_ends_at"
                )
            if data.ends_at is not None and _aware(data.ends_at) <= _utcnow() and exp.status == "draft":
                raise UnprocessableEntityError(
                    "ends_at must be in the future", code="invalid_ends_at"
                )
            exp.ends_at = data.ends_at
        exp.updated_at = _utcnow()
        self._session.commit()
        self._session.refresh(exp)
        return exp

    # ── lifecycle ─────────────────────────────────────────────────────────

    def transition_experiment(
        self,
        experiment_id: str,
        strategy_id_or_slug: str,
        transition: ExperimentTransition,
        project_id: str,
        actor: str,
    ) -> Experiment:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)
        # Serialize lifecycle transitions on the experiment row so concurrent
        # requests cannot interleave status checks/history writes. On
        # PostgreSQL this takes a row lock (SELECT ... FOR UPDATE); on SQLite
        # it is a no-op.
        locked = self._session.scalar(
            select(Experiment)
            .where(Experiment.id == exp.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked is None:
            raise NotFoundError(f"Experiment '{experiment_id}' not found")
        return self._apply_transition(locked, transition, project_id, actor)

    def _apply_transition(
        self, exp: Experiment, transition: ExperimentTransition, project_id: str, actor: str
    ) -> Experiment:
        current = exp.status
        target = transition.status

        if current == target:
            raise ConflictError(
                f"Experiment is already '{current}'", code="invalid_status_transition"
            )
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ConflictError(
                f"Cannot transition experiment from '{current}' to '{target}'. Allowed: {sorted(allowed)}",
                code="invalid_status_transition",
            )
        if (current, target) in REASON_REQUIRED_TRANSITIONS:
            if not transition.reason or len(transition.reason.strip()) < 10:
                raise UnprocessableEntityError(
                    f"Transition '{current}' → '{target}' requires a reason of at least 10 characters",
                    code="missing_transition_reason",
                )
        if target == "running" and exp.started_at is None:
            exp.started_at = _utcnow()
            if exp.ends_at is not None and _aware(exp.ends_at) <= _aware(exp.started_at):
                raise UnprocessableEntityError(
                    "ends_at must be after the experiment start time",
                    code="invalid_ends_at",
                )
        exp.status = target
        exp.updated_at = _utcnow()
        self._record_history(
            exp, current, target, actor,
            transition.reason.strip() if transition.reason else None,
            {},
        )
        self._session.commit()
        self._session.refresh(exp)
        return exp

    def get_history(
        self, experiment_id: str, strategy_id_or_slug: str, project_id: str
    ) -> Sequence[ExperimentStatusHistory]:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)
        return self._session.scalars(
            select(ExperimentStatusHistory)
            .where(
                (ExperimentStatusHistory.experiment_id == exp.id)
                & (ExperimentStatusHistory.project_id == project_id)
            )
            .order_by(
                ExperimentStatusHistory.seq,
                ExperimentStatusHistory.created_at,
                ExperimentStatusHistory.id,
            )
        ).all()

    # ── outcomes (append-only) ────────────────────────────────────────────

    def record_outcome(
        self,
        experiment_id: str,
        strategy_id_or_slug: str,
        data: ExperimentOutcomeCreate,
        project_id: str,
        actor: str,
    ) -> ExperimentOutcome:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)
        if exp.status in {"draft", "cancelled"}:
            raise ConflictError(
                f"Cannot record outcomes while experiment is '{exp.status}'",
                code="invalid_experiment_state",
            )
        if data.observed_at > _utcnow():
            raise UnprocessableEntityError(
                "observed_at cannot be in the future", code="invalid_observed_at"
            )
        if exp.started_at and _aware(data.observed_at) < _aware(exp.started_at):
            raise UnprocessableEntityError(
                "observed_at cannot be before the experiment started", code="invalid_observed_at"
            )
        if data.supersedes_id:
            superseded = self._session.scalar(
                select(ExperimentOutcome).where(
                    (ExperimentOutcome.id == data.supersedes_id)
                    & (ExperimentOutcome.experiment_id == exp.id)
                    & (ExperimentOutcome.project_id == project_id)
                )
            )
            if superseded is None:
                raise NotFoundError(
                    f"Outcome '{data.supersedes_id}' not found for this experiment"
                )
            already = self._session.scalar(
                select(func.count())
                .select_from(ExperimentOutcome)
                .where(ExperimentOutcome.supersedes_id == superseded.id)
            )
            if already:
                raise ConflictError(
                    "That outcome has already been superseded", code="already_superseded"
                )
        outcome = ExperimentOutcome(
            id=str(uuid.uuid4()),
            experiment_id=exp.id,
            project_id=project_id,
            metric_name=data.metric_name.strip(),
            value=data.value,
            sample_size=data.sample_size,
            observed_at=data.observed_at,
            source=data.source,
            source_ref=data.source_ref,
            notes=data.notes,
            actor=actor,
            supersedes_id=data.supersedes_id,
        )
        self._session.add(outcome)
        self._session.commit()
        self._session.refresh(outcome)
        return outcome

    def list_outcomes(
        self,
        experiment_id: str,
        strategy_id_or_slug: str,
        project_id: str,
        metric_name: str | None = None,
    ) -> Sequence[ExperimentOutcome]:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)
        stmt = (
            select(ExperimentOutcome)
            .where(
                (ExperimentOutcome.experiment_id == exp.id)
                & (ExperimentOutcome.project_id == project_id)
            )
            .order_by(ExperimentOutcome.observed_at, ExperimentOutcome.created_at)
        )
        if metric_name:
            stmt = stmt.where(ExperimentOutcome.metric_name == metric_name)
        return self._session.scalars(stmt).all()

    # ── evaluation (append-only) ──────────────────────────────────────────

    def evaluate(
        self, experiment_id: str, strategy_id_or_slug: str, project_id: str, actor: str
    ) -> ExperimentEvaluation:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)
        if exp.status not in {"running", "completed"}:
            raise ConflictError(
                f"Experiment must be 'running' or 'completed' to evaluate (is '{exp.status}')",
                code="invalid_experiment_state",
            )
        criteria = (exp.success_criteria_json or {}).get("criteria")
        if not criteria:
            raise UnprocessableEntityError(
                "Experiment has no success criteria to evaluate against",
                code="missing_success_criteria",
            )
        # Exclude superseded outcomes: an outcome is superseded when another
        # outcome references it via supersedes_id.
        superseded_ids = set(
            self._session.scalars(
                select(ExperimentOutcome.supersedes_id).where(
                    ExperimentOutcome.experiment_id == exp.id
                )
            ).all()
        )
        outcomes = [
            o
            for o in self._session.scalars(
                select(ExperimentOutcome).where(
                    (ExperimentOutcome.experiment_id == exp.id)
                    & (ExperimentOutcome.project_id == project_id)
                )
            ).all()
            if o.id not in superseded_ids
        ]
        result = evaluate_experiment(
            criteria=criteria,
            outcomes=outcomes,
            started_at=exp.started_at,
            ends_at=exp.ends_at,
        )
        evaluation = ExperimentEvaluation(
            id=str(uuid.uuid4()),
            experiment_id=exp.id,
            project_id=project_id,
            verdict=result.verdict,
            rationale_json=result.rationale,
            evaluated_at=_utcnow(),
            actor=actor,
        )
        self._session.add(evaluation)
        self._session.commit()
        self._session.refresh(evaluation)
        return evaluation

    def list_evaluations(
        self, experiment_id: str, strategy_id_or_slug: str, project_id: str
    ) -> Sequence[ExperimentEvaluation]:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        exp = self._resolve_experiment(experiment_id, strategy.id, project_id)
        return self._session.scalars(
            select(ExperimentEvaluation)
            .where(
                (ExperimentEvaluation.experiment_id == exp.id)
                & (ExperimentEvaluation.project_id == project_id)
            )
            .order_by(ExperimentEvaluation.evaluated_at, ExperimentEvaluation.created_at)
        ).all()

    def _record_history(
        self,
        exp: Experiment,
        previous: str | None,
        new: str,
        actor: str,
        reason: str | None,
        metadata_json: dict[str, Any] | None,
    ) -> None:
        next_seq = (
            self._session.scalar(
                select(func.coalesce(func.max(ExperimentStatusHistory.seq), 0)).where(
                    ExperimentStatusHistory.experiment_id == exp.id
                )
            )
            or 0
        ) + 1
        self._session.add(
            ExperimentStatusHistory(
                id=str(uuid.uuid4()),
                experiment_id=exp.id,
                project_id=exp.project_id,
                previous_status=previous,
                new_status=new,
                reason=reason,
                actor=actor,
                seq=next_seq,
                system_metadata_json=metadata_json,
            )
        )
