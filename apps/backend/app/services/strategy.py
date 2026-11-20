import re
import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import (
    GrowthOpportunity,
    GrowthStrategy,
    StrategyGoal,
    StrategyOpportunityAssociation,
    StrategyStatusHistory,
)
from app.schemas.strategy import (
    GrowthStrategyCreate,
    GrowthStrategyTransition,
    GrowthStrategyUpdate,
)
from app.schemas.strategy_association import StrategyOpportunityAssociateItem

ALLOWED_STRATEGY_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_review", "archived"},
    "in_review": {"approved", "draft", "archived"},
    "approved": {"active", "draft", "archived"},
    "active": {"completed", "in_review", "archived"},
    "completed": {"archived"},
    "archived": {"draft"},
}

REASON_REQUIRED_STRATEGY_TRANSITIONS: set[tuple[str, str]] = {
    ("in_review", "draft"),
    ("approved", "draft"),
    ("active", "in_review"),
    ("archived", "draft"),
    ("draft", "archived"),
    ("in_review", "archived"),
    ("approved", "archived"),
    ("active", "archived"),
    ("completed", "archived"),
}


def generate_strategy_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    cleaned = cleaned[:200].rstrip("-")
    return cleaned or f"strat-{uuid.uuid4().hex[:6]}"


class StrategyService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_strategies(
        self,
        project_id: str,
        status: str | None = None,
        time_horizon: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[GrowthStrategy], int]:
        base_query = select(GrowthStrategy).where(GrowthStrategy.project_id == project_id)
        count_query = (
            select(func.count())
            .select_from(GrowthStrategy)
            .where(GrowthStrategy.project_id == project_id)
        )

        if status:
            base_query = base_query.where(GrowthStrategy.status == status)
            count_query = count_query.where(GrowthStrategy.status == status)
        if time_horizon:
            base_query = base_query.where(GrowthStrategy.time_horizon == time_horizon)
            count_query = count_query.where(GrowthStrategy.time_horizon == time_horizon)

        total = self._session.scalar(count_query) or 0
        items_query = (
            base_query.order_by(GrowthStrategy.created_at.desc(), GrowthStrategy.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = self._session.scalars(items_query).all()
        return items, total

    def get_strategy(self, strategy_id_or_slug: str, project_id: str) -> GrowthStrategy:
        stmt = select(GrowthStrategy).where(
            ((GrowthStrategy.id == strategy_id_or_slug) | (GrowthStrategy.slug == strategy_id_or_slug))
            & (GrowthStrategy.project_id == project_id)
        )
        strategy = self._session.scalar(stmt)
        if not strategy:
            raise NotFoundError(f"Growth strategy '{strategy_id_or_slug}' not found in this project")
        return strategy

    def create_strategy(
        self, data: GrowthStrategyCreate, project_id: str, actor: str
    ) -> GrowthStrategy:
        slug = data.slug or generate_strategy_slug(data.name)

        # Check existing slug in this project
        existing = self._session.scalar(
            select(GrowthStrategy).where(
                (GrowthStrategy.project_id == project_id) & (GrowthStrategy.slug == slug)
            )
        )
        if existing:
            if data.slug:
                raise ConflictError(
                    f"Growth strategy with slug '{slug}' already exists in this project",
                    code="slug_conflict",
                )
            base_slug = slug[:190].rstrip("-")
            counter = 1
            max_attempts = 100
            while existing and counter <= max_attempts:
                slug = f"{base_slug}-{counter}"
                existing = self._session.scalar(
                    select(GrowthStrategy).where(
                        (GrowthStrategy.project_id == project_id) & (GrowthStrategy.slug == slug)
                    )
                )
                counter += 1
            if existing:
                slug = f"{base_slug[:180].rstrip('-')}-{uuid.uuid4().hex[:8]}"

        strat_id = str(uuid.uuid4())
        strategy = GrowthStrategy(
            id=strat_id,
            project_id=project_id,
            name=data.name,
            slug=slug,
            description=data.description,
            strategic_vision=data.strategic_vision,
            target_audience=data.target_audience,
            strategic_constraints=data.strategic_constraints,
            budget_envelope=data.budget_envelope,
            currency=data.currency,
            time_horizon=data.time_horizon,
            status="draft",
            metadata_json=data.metadata_json,
        )

        try:
            self._session.add(strategy)
            self._session.commit()
            self._session.refresh(strategy)
            return strategy
        except IntegrityError as exc:
            self._session.rollback()
            orig_msg = str(getattr(exc, "orig", exc)).lower()
            if "uq_growth_strategies_project_slug" in orig_msg or (
                "unique" in orig_msg and "slug" in orig_msg
            ):
                raise ConflictError(
                    f"Growth strategy with slug '{slug}' already exists in this project",
                    code="slug_conflict",
                ) from exc
            raise

    def update_strategy(
        self,
        strategy_id_or_slug: str,
        data: GrowthStrategyUpdate,
        project_id: str,
        actor: str,
    ) -> GrowthStrategy:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)

        # Disallow arbitrary status modification through ordinary update
        if data.status is not None and data.status != strategy.status:
            raise ConflictError(
                "Lifecycle status cannot be modified via ordinary update. Use the transition endpoint.",
                code="invalid_status_transition",
            )

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field in ("status", "reason"):
                continue
            if field == "metadata_json":
                strategy.metadata_json = value
            elif hasattr(strategy, field):
                setattr(strategy, field, value)

        strategy.updated_at = datetime.now(timezone.utc)

        try:
            self._session.commit()
            self._session.refresh(strategy)
            return strategy
        except Exception:
            self._session.rollback()
            raise

    def transition_strategy(
        self,
        strategy_id_or_slug: str,
        transition: GrowthStrategyTransition,
        project_id: str,
        actor: str,
    ) -> GrowthStrategy:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)
        current_status = strategy.status
        target_status = transition.status

        if current_status == target_status:
            raise ConflictError(
                f"Growth strategy is already in status '{current_status}'",
                code="invalid_status_transition",
            )

        allowed = ALLOWED_STRATEGY_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ConflictError(
                f"Cannot transition strategy from '{current_status}' to '{target_status}'. Allowed targets: {sorted(list(allowed))}",
                code="invalid_status_transition",
            )

        # Enforce mandatory justification reasons
        if (current_status, target_status) in REASON_REQUIRED_STRATEGY_TRANSITIONS:
            if not transition.reason or len(transition.reason.strip()) < 10:
                raise UnprocessableEntityError(
                    f"Transition from '{current_status}' to '{target_status}' requires an explanatory reason of at least 10 characters",
                    code="missing_transition_reason",
                )

        # Opportunity Revalidation Rules
        associated_opps_stmt = (
            select(GrowthOpportunity)
            .join(
                StrategyOpportunityAssociation,
                (StrategyOpportunityAssociation.opportunity_id == GrowthOpportunity.id)
                & (StrategyOpportunityAssociation.project_id == GrowthOpportunity.project_id),
            )
            .where(StrategyOpportunityAssociation.strategy_id == strategy.id)
        )
        linked_opportunities = self._session.scalars(associated_opps_stmt).all()

        if target_status == "in_review":
            # In review: opportunities cannot be rejected or archived
            for opp in linked_opportunities:
                if opp.status in ("rejected", "archived"):
                    raise UnprocessableEntityError(
                        f"Cannot submit strategy for review: linked opportunity '{opp.title}' is in '{opp.status}' status.",
                        code="invalid_opportunity_state",
                    )

        elif target_status in ("approved", "active"):
            # Approved / Active: every linked opportunity must be approved
            for opp in linked_opportunities:
                if opp.status != "approved":
                    raise UnprocessableEntityError(
                        f"Cannot {target_status} strategy: linked opportunity '{opp.title}' is in '{opp.status}' status. Approved strategies require all linked opportunities to be approved.",
                        code="unapproved_opportunity_linked",
                    )

        strategy.status = target_status
        strategy.updated_at = datetime.now(timezone.utc)

        history = StrategyStatusHistory(
            id=str(uuid.uuid4()),
            strategy_id=strategy.id,
            project_id=project_id,
            previous_status=current_status,
            new_status=target_status,
            reason=transition.reason.strip() if transition.reason else None,
            actor=actor,
            system_metadata_json=transition.metadata_json,
        )

        try:
            self._session.add(history)
            self._session.commit()
            self._session.refresh(strategy)
            return strategy
        except Exception:
            self._session.rollback()
            raise

    def delete_strategy(self, strategy_id_or_slug: str, project_id: str) -> None:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)

        # Guard 1: Only draft strategies can be deleted
        if strategy.status != "draft":
            raise ConflictError(
                "Only draft strategies can be deleted. Archive the strategy instead to preserve the record.",
                code="cannot_delete_active_strategy",
            )

        # Guard 2: Cannot delete if strategy has lifecycle-history records
        history_count = self._session.scalar(
            select(func.count())
            .select_from(StrategyStatusHistory)
            .where(StrategyStatusHistory.strategy_id == strategy.id)
        )
        if history_count and history_count > 0:
            raise ConflictError(
                "Strategies with lifecycle transition history cannot be deleted. Archive the strategy instead to preserve the audit trail.",
                code="cannot_delete_audited_strategy",
            )

        # Guard 3: Cannot delete if active goals are attached
        goals_count = self._session.scalar(
            select(func.count())
            .select_from(StrategyGoal)
            .where(StrategyGoal.strategy_id == strategy.id)
        )
        if goals_count and goals_count > 0:
            raise ConflictError(
                "Cannot delete strategy with attached goals. Delete or reassign goals first.",
                code="cannot_delete_strategy_with_goals",
            )

        # Guard 4: Cannot delete if opportunities are linked
        assoc_count = self._session.scalar(
            select(func.count())
            .select_from(StrategyOpportunityAssociation)
            .where(StrategyOpportunityAssociation.strategy_id == strategy.id)
        )
        if assoc_count and assoc_count > 0:
            raise ConflictError(
                "Cannot delete strategy with linked opportunities. Unlink opportunities first.",
                code="cannot_delete_strategy_with_associations",
            )

        try:
            self._session.delete(strategy)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def get_history(
        self, strategy_id_or_slug: str, project_id: str
    ) -> Sequence[StrategyStatusHistory]:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)
        stmt = (
            select(StrategyStatusHistory)
            .where(
                (StrategyStatusHistory.strategy_id == strategy.id)
                & (StrategyStatusHistory.project_id == project_id)
            )
            .order_by(StrategyStatusHistory.created_at.asc())
        )
        return self._session.scalars(stmt).all()

    # -------------------------------------------------------------------------
    # Opportunity Association Management
    # -------------------------------------------------------------------------

    def associate_opportunities(
        self,
        strategy_id_or_slug: str,
        items: list[StrategyOpportunityAssociateItem],
        project_id: str,
    ) -> list[StrategyOpportunityAssociation]:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)

        if strategy.status in ("completed", "archived"):
            raise ConflictError(
                f"Cannot link opportunities to a strategy in '{strategy.status}' status",
                code="strategy_not_editable",
            )

        results = []
        for item in items:
            stmt = select(GrowthOpportunity).where(
                (GrowthOpportunity.id == item.opportunity_id)
                & (GrowthOpportunity.project_id == project_id)
            )
            opp = self._session.scalar(stmt)
            if not opp:
                raise NotFoundError(
                    f"Growth opportunity '{item.opportunity_id}' not found in this project"
                )

            # Opportunity status validation rules:
            # - Draft strategies may link opportunities in 'in_review' or 'approved'
            # - Approved / Active strategies may ONLY link opportunities in 'approved'
            if strategy.status == "draft":
                if opp.status not in ("in_review", "approved"):
                    raise UnprocessableEntityError(
                        f"Draft strategies can only link opportunities in 'in_review' or 'approved' status. Opportunity '{opp.title}' is '{opp.status}'.",
                        code="invalid_opportunity_status",
                    )
            elif strategy.status in ("approved", "active"):
                if opp.status != "approved":
                    raise UnprocessableEntityError(
                        f"Approved strategies can only link opportunities in 'approved' status. Opportunity '{opp.title}' is '{opp.status}'.",
                        code="invalid_opportunity_status",
                    )

            # Upsert association
            assoc_stmt = select(StrategyOpportunityAssociation).where(
                (StrategyOpportunityAssociation.strategy_id == strategy.id)
                & (StrategyOpportunityAssociation.opportunity_id == opp.id)
            )
            existing_assoc = self._session.scalar(assoc_stmt)
            if existing_assoc:
                existing_assoc.strategic_rationale = item.strategic_rationale
                assoc = existing_assoc
            else:
                assoc = StrategyOpportunityAssociation(
                    strategy_id=strategy.id,
                    opportunity_id=opp.id,
                    project_id=project_id,
                    strategic_rationale=item.strategic_rationale,
                )
                self._session.add(assoc)
            results.append(assoc)

        try:
            self._session.commit()
            for r in results:
                self._session.refresh(r)
            return results
        except Exception:
            self._session.rollback()
            raise

    def list_associated_opportunities(
        self, strategy_id_or_slug: str, project_id: str
    ) -> list[tuple[StrategyOpportunityAssociation, GrowthOpportunity]]:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)
        stmt = (
            select(StrategyOpportunityAssociation, GrowthOpportunity)
            .join(
                GrowthOpportunity,
                (StrategyOpportunityAssociation.opportunity_id == GrowthOpportunity.id)
                & (StrategyOpportunityAssociation.project_id == GrowthOpportunity.project_id),
            )
            .where(StrategyOpportunityAssociation.strategy_id == strategy.id)
            .order_by(StrategyOpportunityAssociation.created_at.desc())
        )
        return list(self._session.execute(stmt).all())

    def unlink_opportunity(
        self, strategy_id_or_slug: str, opportunity_id: str, project_id: str
    ) -> None:
        strategy = self.get_strategy(strategy_id_or_slug, project_id=project_id)
        stmt = select(StrategyOpportunityAssociation).where(
            (StrategyOpportunityAssociation.strategy_id == strategy.id)
            & (StrategyOpportunityAssociation.opportunity_id == opportunity_id)
        )
        assoc = self._session.scalar(stmt)
        if not assoc:
            raise NotFoundError(
                f"Association between strategy '{strategy_id_or_slug}' and opportunity '{opportunity_id}' not found"
            )

        try:
            self._session.delete(assoc)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
