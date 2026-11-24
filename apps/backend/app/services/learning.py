"""Phase 7 learning records: candidate → validated/rejected lifecycle.

Evidence traceability: strategy/experiment links are DB-enforced composite
FKs; outcome/evaluation references in evidence_json are verified at write
time to exist, belong to the same project, and (when an experiment is
linked) belong to that experiment. Only ``validated`` records are returned
by ``get_validated`` — the recommendation-consumption integration point.
"""

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
    GrowthStrategy,
    LearningRecord,
)
from app.schemas.learning import LearningCreate, LearningEvidence, LearningUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LearningService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── resolution / evidence validation ──────────────────────────────────

    def _resolve_strategy(self, strategy_id: str, project_id: str) -> GrowthStrategy:
        strategy = self._session.scalar(
            select(GrowthStrategy).where(
                (GrowthStrategy.id == strategy_id)
                & (GrowthStrategy.project_id == project_id)
            )
        )
        if strategy is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")
        return strategy

    def _resolve_experiment(self, experiment_id: str, project_id: str) -> Experiment:
        exp = self._session.scalar(
            select(Experiment).where(
                (Experiment.id == experiment_id)
                & (Experiment.project_id == project_id)
            )
        )
        if exp is None:
            raise NotFoundError(f"Experiment '{experiment_id}' not found")
        return exp

    def _resolve_learning(self, learning_id: str, project_id: str) -> LearningRecord:
        rec = self._session.scalar(
            select(LearningRecord).where(
                (LearningRecord.id == learning_id)
                & (LearningRecord.project_id == project_id)
            )
        )
        if rec is None:
            raise NotFoundError(f"Learning record '{learning_id}' not found")
        return rec

    def _build_evidence_json(
        self,
        evidence: LearningEvidence | None,
        experiment_id: str | None,
        project_id: str,
    ) -> dict[str, Any] | None:
        """Verify every referenced record exists and belongs to this project."""
        if evidence is None or (not evidence.outcome_ids and not evidence.evaluation_ids):
            return None
        if not experiment_id:
            raise UnprocessableEntityError(
                "outcome/evaluation evidence requires a linked experiment_id",
                code="evidence_requires_experiment",
            )
        exp = self._resolve_experiment(experiment_id, project_id)

        outcome_ids: list[str] = []
        for oid in dict.fromkeys(evidence.outcome_ids):
            row = self._session.scalar(
                select(ExperimentOutcome).where(
                    (ExperimentOutcome.id == oid)
                    & (ExperimentOutcome.project_id == project_id)
                    & (ExperimentOutcome.experiment_id == exp.id)
                )
            )
            if row is None:
                raise NotFoundError(
                    f"Outcome '{oid}' not found for this experiment"
                )
            outcome_ids.append(row.id)

        evaluation_ids: list[str] = []
        for eid in dict.fromkeys(evidence.evaluation_ids):
            row = self._session.scalar(
                select(ExperimentEvaluation).where(
                    (ExperimentEvaluation.id == eid)
                    & (ExperimentEvaluation.project_id == project_id)
                    & (ExperimentEvaluation.experiment_id == exp.id)
                )
            )
            if row is None:
                raise NotFoundError(
                    f"Evaluation '{eid}' not found for this experiment"
                )
            evaluation_ids.append(row.id)

        return {"outcome_ids": outcome_ids, "evaluation_ids": evaluation_ids}

    def _resolve_links(
        self,
        strategy_id: str | None,
        experiment_id: str | None,
        project_id: str,
        current: LearningRecord | None = None,
    ) -> tuple[str | None, str | None]:
        """Resolve optional strategy/experiment links with consistency checks."""
        # Determine effective values: explicit arg wins; None means "leave as-is"
        # is handled by callers via model_fields_set, so here None = clear only
        # when caller intends. Callers pass resolved values already.
        exp = None
        if experiment_id:
            exp = self._resolve_experiment(experiment_id, project_id)
        strat = None
        if strategy_id:
            strat = self._resolve_strategy(strategy_id, project_id)
        if exp is not None and strat is not None and exp.strategy_id != strat.id:
            raise UnprocessableEntityError(
                "Linked experiment does not belong to the linked strategy",
                code="inconsistent_links",
            )
        if exp is not None and strategy_id is None and current is not None:
            # keep existing strategy link consistent
            pass
        return (strat.id if strat else strategy_id), (exp.id if exp else experiment_id)

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create(
        self, data: LearningCreate, project_id: str, actor: str
    ) -> LearningRecord:
        strategy_id, experiment_id = self._resolve_links(
            data.strategy_id, data.experiment_id, project_id
        )
        evidence_json = self._build_evidence_json(
            data.evidence, experiment_id, project_id
        )
        rec = LearningRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            strategy_id=strategy_id,
            experiment_id=experiment_id,
            title=data.title.strip(),
            insight=data.insight.strip(),
            category=data.category,
            status="candidate",
            evidence_json=evidence_json,
        )
        self._session.add(rec)
        self._session.commit()
        self._session.refresh(rec)
        return rec

    def list(
        self,
        project_id: str,
        strategy_id: str | None = None,
        experiment_id: str | None = None,
        category: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[LearningRecord], int]:
        if status is not None and status not in {"candidate", "validated", "rejected"}:
            raise UnprocessableEntityError(
                f"Invalid status filter '{status}'", code="invalid_status_filter"
            )
        base = select(LearningRecord).where(LearningRecord.project_id == project_id)
        count_q = (
            select(func.count())
            .select_from(LearningRecord)
            .where(LearningRecord.project_id == project_id)
        )
        for col, val in (
            (LearningRecord.strategy_id, strategy_id),
            (LearningRecord.experiment_id, experiment_id),
            (LearningRecord.category, category),
            (LearningRecord.status, status),
        ):
            if val is not None:
                base = base.where(col == val)
                count_q = count_q.where(col == val)
        total = self._session.scalar(count_q) or 0
        items = self._session.scalars(
            base.order_by(LearningRecord.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return items, total

    def get(self, learning_id: str, project_id: str) -> LearningRecord:
        return self._resolve_learning(learning_id, project_id)

    def update(
        self, learning_id: str, data: LearningUpdate, project_id: str, actor: str
    ) -> LearningRecord:
        rec = self._resolve_learning(learning_id, project_id)
        if rec.status != "candidate":
            raise ConflictError(
                f"Learning record is '{rec.status}' and cannot be modified",
                code="learning_not_editable",
            )
        fields = data.model_fields_set
        if "title" in fields and data.title is not None:
            rec.title = data.title.strip()
        if "insight" in fields and data.insight is not None:
            rec.insight = data.insight.strip()
        if "category" in fields:
            rec.category = data.category

        new_strategy = rec.strategy_id
        new_experiment = rec.experiment_id
        if "strategy_id" in fields or "experiment_id" in fields:
            s_arg = data.strategy_id if "strategy_id" in fields else rec.strategy_id
            e_arg = data.experiment_id if "experiment_id" in fields else rec.experiment_id
            # Sentinel: explicit null clears the link
            new_strategy, new_experiment = self._resolve_links(
                s_arg, e_arg, project_id, current=rec
            )
            # If experiment provided without strategy, inherit experiment's strategy
            if e_arg and "strategy_id" not in fields:
                exp = self._resolve_experiment(e_arg, project_id)
                new_strategy = exp.strategy_id
        if "evidence" in fields:
            rec.evidence_json = self._build_evidence_json(
                data.evidence, new_experiment, project_id
            )
        rec.strategy_id = new_strategy
        rec.experiment_id = new_experiment
        rec.updated_at = _utcnow()
        self._session.commit()
        self._session.refresh(rec)
        return rec

    # ── lifecycle ─────────────────────────────────────────────────────────

    def validate(self, learning_id: str, project_id: str, actor: str) -> LearningRecord:
        rec = self._resolve_learning(learning_id, project_id)
        if rec.status != "candidate":
            raise ConflictError(
                f"Cannot validate a '{rec.status}' learning record",
                code="invalid_learning_transition",
            )
        rec.status = "validated"
        rec.validated_by = actor
        rec.validated_at = _utcnow()
        rec.updated_at = _utcnow()
        self._session.commit()
        self._session.refresh(rec)
        return rec

    def reject(
        self, learning_id: str, reason: str, project_id: str, actor: str
    ) -> LearningRecord:
        rec = self._resolve_learning(learning_id, project_id)
        if rec.status != "candidate":
            raise ConflictError(
                f"Cannot reject a '{rec.status}' learning record",
                code="invalid_learning_transition",
            )
        rec.status = "rejected"
        rec.rejected_by = actor
        rec.rejected_at = _utcnow()
        rec.rejection_reason = reason.strip()
        rec.updated_at = _utcnow()
        self._session.commit()
        self._session.refresh(rec)
        return rec

    # ── recommendation integration point ─────────────────────────────────

    def get_validated(
        self,
        project_id: str,
        strategy_id: str | None = None,
        experiment_id: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[LearningRecord], int]:
        """Established learnings for recommendation workflows.

        Only ``validated`` records are returned — candidate and rejected
        records are never exposed as established learning. This is the
        service-level integration point consumed by future recommendation
        features; it performs no rewriting of existing workflows.
        """
        return self.list(
            project_id,
            strategy_id=strategy_id,
            experiment_id=experiment_id,
            category=category,
            status="validated",
            limit=limit,
            offset=offset,
        )
