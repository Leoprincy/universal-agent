import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.database.models import (
    GoalMetricUpdate,
    GoalStatusHistory,
    GrowthStrategy,
    StrategyGoal,
)
from app.schemas.goal import (
    GoalMetricUpdateCreate,
    StrategyGoalCreate,
    StrategyGoalUpdate,
    compute_goal_progress,
)


class GoalService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _resolve_strategy(self, strategy_id_or_slug: str, project_id: str) -> GrowthStrategy:
        stmt = select(GrowthStrategy).where(
            ((GrowthStrategy.id == strategy_id_or_slug) | (GrowthStrategy.slug == strategy_id_or_slug))
            & (GrowthStrategy.project_id == project_id)
        )
        strategy = self._session.scalar(stmt)
        if not strategy:
            raise NotFoundError(f"Growth strategy '{strategy_id_or_slug}' not found in this project")
        return strategy

    def _get_scoped_goal(
        self, goal_id: str, strategy_id: str, project_id: str
    ) -> StrategyGoal:
        stmt = select(StrategyGoal).where(
            (StrategyGoal.id == goal_id)
            & (StrategyGoal.strategy_id == strategy_id)
            & (StrategyGoal.project_id == project_id)
        )
        goal = self._session.scalar(stmt)
        if not goal:
            raise NotFoundError(f"Strategy goal '{goal_id}' not found in this project")
        return goal

    def _record_status_change(
        self,
        goal: StrategyGoal,
        previous_status: str,
        new_status: str,
        actor: str,
        reason: str | None = None,
        system_metadata: dict | None = None,
    ) -> None:
        if previous_status == new_status:
            return
        self._session.add(
            GoalStatusHistory(
                id=str(uuid.uuid4()),
                goal_id=goal.id,
                project_id=goal.project_id,
                previous_status=previous_status,
                new_status=new_status,
                reason=reason,
                actor=actor,
                system_metadata_json=system_metadata,
            )
        )

    def list_goals(
        self, strategy_id_or_slug: str, project_id: str, status: str | None = None
    ) -> Sequence[StrategyGoal]:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)
        stmt = select(StrategyGoal).where(
            (StrategyGoal.strategy_id == strategy.id) & (StrategyGoal.project_id == project_id)
        )
        if status:
            stmt = stmt.where(StrategyGoal.status == status)
        stmt = stmt.order_by(StrategyGoal.created_at.asc())
        return self._session.scalars(stmt).all()

    def get_goal(self, goal_id: str, strategy_id: str, project_id: str) -> StrategyGoal:
        return self._get_scoped_goal(goal_id, strategy_id, project_id)

    def create_goal(
        self, strategy_id_or_slug: str, data: StrategyGoalCreate, project_id: str, actor: str
    ) -> StrategyGoal:
        strategy = self._resolve_strategy(strategy_id_or_slug, project_id)

        current_val = data.current_value if data.current_value is not None else data.baseline_value

        goal = StrategyGoal(
            id=str(uuid.uuid4()),
            project_id=project_id,
            strategy_id=strategy.id,
            name=data.name,
            description=data.description,
            metric_name=data.metric_name,
            metric_unit=data.metric_unit,
            baseline_value=data.baseline_value,
            current_value=current_val,
            target_value=data.target_value,
            deadline=data.deadline,
            status="pending",
            metadata_json=data.metadata_json,
        )

        self._session.add(goal)
        self._session.flush()
        self._record_status_change(
            goal,
            previous_status=None,
            new_status="pending",
            actor=actor,
            reason="Initial goal creation",
        )

        try:
            self._session.commit()
            self._session.refresh(goal)
            return goal
        except Exception:
            self._session.rollback()
            raise

    def update_goal(
        self,
        goal_id: str,
        strategy_id: str,
        data: StrategyGoalUpdate,
        project_id: str,
        actor: str,
    ) -> StrategyGoal:
        goal = self._get_scoped_goal(goal_id, strategy_id, project_id)
        previous_status = goal.status

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field in ("status", "reason"):
                continue
            if field == "metadata_json":
                goal.metadata_json = value
            elif hasattr(goal, field):
                setattr(goal, field, value)

        if data.status is not None and data.status != previous_status:
            goal.status = data.status
            self._record_status_change(
                goal,
                previous_status=previous_status,
                new_status=data.status,
                actor=actor,
                reason=data.reason,
            )

        goal.updated_at = datetime.now(timezone.utc)

        try:
            self._session.commit()
            self._session.refresh(goal)
            return goal
        except Exception:
            self._session.rollback()
            raise

    def delete_goal(self, goal_id: str, strategy_id: str, project_id: str) -> None:
        goal = self._get_scoped_goal(goal_id, strategy_id, project_id)

        history_count = self._session.scalar(
            select(func.count())
            .select_from(GoalStatusHistory)
            .where(GoalStatusHistory.goal_id == goal.id)
        )
        if history_count and history_count > 0:
            raise ConflictError(
                "Goals with status history cannot be deleted. Set status to 'abandoned' instead to preserve the audit trail.",
                code="cannot_delete_audited_goal",
            )

        metric_count = self._session.scalar(
            select(func.count())
            .select_from(GoalMetricUpdate)
            .where(GoalMetricUpdate.goal_id == goal.id)
        )
        if metric_count and metric_count > 0:
            raise ConflictError(
                "Goals with metric progress history cannot be deleted. Update status to 'abandoned' instead.",
                code="cannot_delete_goal_with_history",
            )

        try:
            self._session.delete(goal)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def record_progress(
        self, goal_id: str, strategy_id: str, data: GoalMetricUpdateCreate, project_id: str, actor: str
    ) -> tuple[StrategyGoal, GoalMetricUpdate]:
        goal = self._get_scoped_goal(goal_id, strategy_id, project_id)
        previous_val = float(goal.current_value)
        new_val = float(data.new_value)
        previous_status = goal.status

        # Create append-only metric update
        update_record = GoalMetricUpdate(
            id=str(uuid.uuid4()),
            goal_id=goal.id,
            project_id=project_id,
            previous_value=previous_val,
            new_value=new_val,
            notes=data.notes.strip() if data.notes else None,
            actor=actor,
        )

        goal.current_value = new_val
        goal.updated_at = datetime.now(timezone.utc)

        # Rule-based status evaluation
        baseline = float(goal.baseline_value)
        target = float(goal.target_value)
        progress_pct, is_increasing = compute_goal_progress(baseline, target, new_val)

        if goal.status != "abandoned":
            if is_increasing and new_val >= target:
                goal.status = "achieved"
            elif not is_increasing and new_val <= target:
                goal.status = "achieved"
            elif goal.deadline and datetime.now(timezone.utc) > goal.deadline:
                goal.status = "behind"
            elif progress_pct < 0:
                goal.status = "at_risk"
            elif goal.status == "pending" and new_val != baseline:
                goal.status = "on_track"

        if goal.status != previous_status:
            self._record_status_change(
                goal,
                previous_status=previous_status,
                new_status=goal.status,
                actor=actor,
                system_metadata={"trigger": "progress_update"},
            )

        try:
            self._session.add(update_record)
            self._session.commit()
            self._session.refresh(goal)
            self._session.refresh(update_record)
            return goal, update_record
        except Exception:
            self._session.rollback()
            raise

    def get_metric_history(
        self, goal_id: str, strategy_id: str, project_id: str
    ) -> Sequence[GoalMetricUpdate]:
        goal = self._get_scoped_goal(goal_id, strategy_id, project_id)
        stmt = (
            select(GoalMetricUpdate)
            .where((GoalMetricUpdate.goal_id == goal.id) & (GoalMetricUpdate.project_id == project_id))
            .order_by(GoalMetricUpdate.created_at.desc())
        )
        return self._session.scalars(stmt).all()

    def get_status_history(
        self, goal_id: str, strategy_id: str, project_id: str
    ) -> Sequence[GoalStatusHistory]:
        goal = self._get_scoped_goal(goal_id, strategy_id, project_id)
        stmt = (
            select(GoalStatusHistory)
            .where((GoalStatusHistory.goal_id == goal.id) & (GoalStatusHistory.project_id == project_id))
            .order_by(GoalStatusHistory.created_at.asc())
        )
        return self._session.scalars(stmt).all()
