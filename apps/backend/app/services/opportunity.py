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
    OpportunityResearchAssociation,
    OpportunityStatusHistory,
    ResearchRecord,
    StrategyOpportunityAssociation,
)
from app.schemas.association import AssociationItem
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityStatus,
    OpportunityTransition,
    OpportunityUpdate,
    calculate_priority,
)


def generate_slug(title: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    cleaned = cleaned[:200].rstrip("-")
    return cleaned or f"opp-{uuid.uuid4().hex[:6]}"


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_review", "archived"},
    "in_review": {"approved", "rejected", "draft", "archived"},
    "approved": {"archived"},
    "rejected": {"draft", "archived"},
    "archived": set(),
}

REASON_REQUIRED_TRANSITIONS: set[tuple[str, str]] = {
    ("in_review", "rejected"),
    ("in_review", "draft"),
    ("rejected", "draft"),
}


class OpportunityService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_opportunities(
        self,
        project_id: str,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[GrowthOpportunity], int]:
        base_query = select(GrowthOpportunity).where(GrowthOpportunity.project_id == project_id)
        count_query = (
            select(func.count())
            .select_from(GrowthOpportunity)
            .where(GrowthOpportunity.project_id == project_id)
        )

        if status:
            base_query = base_query.where(GrowthOpportunity.status == status)
            count_query = count_query.where(GrowthOpportunity.status == status)
        if category:
            base_query = base_query.where(GrowthOpportunity.category == category)
            count_query = count_query.where(GrowthOpportunity.category == category)
        if priority:
            base_query = base_query.where(GrowthOpportunity.priority == priority)
            count_query = count_query.where(GrowthOpportunity.priority == priority)

        total = self._session.scalar(count_query) or 0
        items_query = (
            base_query.order_by(GrowthOpportunity.created_at.desc(), GrowthOpportunity.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = self._session.scalars(items_query).all()
        return items, total

    def get_opportunity(self, opp_id_or_slug: str, project_id: str) -> GrowthOpportunity:
        stmt = select(GrowthOpportunity).where(
            ((GrowthOpportunity.id == opp_id_or_slug) | (GrowthOpportunity.slug == opp_id_or_slug))
            & (GrowthOpportunity.project_id == project_id)
        )
        opp = self._session.scalar(stmt)
        if not opp:
            raise NotFoundError(f"Opportunity '{opp_id_or_slug}' not found in this project")
        return opp

    def create_opportunity(
        self, data: OpportunityCreate, project_id: str, actor: str
    ) -> GrowthOpportunity:
        slug = data.slug or generate_slug(data.title)

        # Check existing slug in the same project
        existing = self._session.scalar(
            select(GrowthOpportunity).where(
                (GrowthOpportunity.project_id == project_id) & (GrowthOpportunity.slug == slug)
            )
        )
        if existing:
            if data.slug:
                raise ConflictError(
                    f"Opportunity with slug '{slug}' already exists in this project",
                    code="slug_conflict",
                )
            base_slug = slug[:190].rstrip("-")
            counter = 1
            max_attempts = 100
            while existing and counter <= max_attempts:
                slug = f"{base_slug}-{counter}"
                existing = self._session.scalar(
                    select(GrowthOpportunity).where(
                        (GrowthOpportunity.project_id == project_id) & (GrowthOpportunity.slug == slug)
                    )
                )
                counter += 1
            if existing:
                slug = f"{base_slug[:180].rstrip('-')}-{uuid.uuid4().hex[:8]}"

        priority = calculate_priority(data.estimated_impact, data.estimated_effort)
        opp_id = str(uuid.uuid4())

        opp = GrowthOpportunity(
            id=opp_id,
            project_id=project_id,
            title=data.title,
            slug=slug,
            problem_statement=data.problem_statement,
            hypothesis=data.hypothesis,
            proposed_mechanism=data.proposed_mechanism,
            target_audience=data.target_audience,
            category=data.category,
            status="draft",
            estimated_impact=data.estimated_impact,
            estimated_effort=data.estimated_effort,
            confidence_score=data.confidence_score,
            priority=priority,
            metadata_json=data.metadata_json,
        )

        history = OpportunityStatusHistory(
            id=str(uuid.uuid4()),
            opportunity_id=opp_id,
            project_id=project_id,
            previous_status=None,
            new_status="draft",
            reason="Initial draft creation",
            actor=actor,
            system_metadata_json=None,
        )

        try:
            self._session.add(opp)
            self._session.add(history)
            self._session.commit()
            self._session.refresh(opp)
            return opp
        except IntegrityError as exc:
            self._session.rollback()
            orig_msg = str(getattr(exc, "orig", exc)).lower()
            if "uq_growth_opportunities_project_slug" in orig_msg or (
                "unique" in orig_msg and "slug" in orig_msg
            ):
                raise ConflictError(
                    f"Opportunity with slug '{slug}' already exists in this project",
                    code="slug_conflict",
                ) from exc
            raise

    def _apply_transition(
        self,
        opp: GrowthOpportunity,
        target_status: str,
        reason: str | None,
        metadata_json: dict | None,
        actor: str,
        project_id: str,
    ) -> None:
        """Validate and apply a lifecycle transition without committing.

        Flushes pending changes so callers can compose this with other writes
        inside a single transaction.
        """
        current_status = opp.status
        target_status = str(target_status)

        if current_status == target_status:
            raise ConflictError(
                f"Opportunity is already in status '{current_status}'",
                code="invalid_status_transition",
            )

        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ConflictError(
                f"Cannot transition opportunity from '{current_status}' to '{target_status}'. Allowed targets: {sorted(list(allowed))}",
                code="invalid_status_transition",
            )

        if (current_status, target_status) in REASON_REQUIRED_TRANSITIONS:
            if not reason or len(reason.strip()) < 10:
                raise UnprocessableEntityError(
                    f"Transition from '{current_status}' to '{target_status}' requires an explanatory reason of at least 10 characters",
                    code="missing_transition_reason",
                )

        # Guard: the target status must keep the opportunity eligible for
        # every strategy it is linked to. Draft and in-review strategies
        # require opportunities in in_review or approved; approved and
        # active strategies require approved opportunities. The user can
        # resolve a conflict by unlinking the opportunity or revising the
        # strategy through the supported association endpoints.
        linked_statuses = self._session.scalars(
            select(GrowthStrategy.status)
            .join(
                StrategyOpportunityAssociation,
                (StrategyOpportunityAssociation.strategy_id == GrowthStrategy.id)
                & (StrategyOpportunityAssociation.project_id == GrowthStrategy.project_id),
            )
            .where(
                (StrategyOpportunityAssociation.opportunity_id == opp.id)
                & (StrategyOpportunityAssociation.project_id == project_id)
                & (GrowthStrategy.status.in_(["draft", "in_review", "approved", "active"]))
            )
        ).all()
        for strategy_status in linked_statuses:
            eligible = (
                {"in_review", "approved"}
                if strategy_status in ("draft", "in_review")
                else {"approved"}
            )
            if target_status not in eligible:
                raise ConflictError(
                    f"Cannot transition this opportunity to '{target_status}': it is linked to a '{strategy_status}' growth strategy that requires opportunities in {sorted(eligible)}. Unlink it or revise the strategy first.",
                    code="opportunity_linked_to_active_strategy",
                )

        opp.status = target_status
        opp.updated_at = datetime.now(timezone.utc)

        history = OpportunityStatusHistory(
            id=str(uuid.uuid4()),
            opportunity_id=opp.id,
            project_id=project_id,
            previous_status=current_status,
            new_status=target_status,
            reason=reason.strip() if reason else None,
            actor=actor,
            system_metadata_json=metadata_json,
        )
        self._session.add(history)
        self._session.flush()

    def transition_opportunity(
        self,
        opp_id_or_slug: str,
        transition: OpportunityTransition,
        project_id: str,
        actor: str,
    ) -> GrowthOpportunity:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)

        try:
            self._apply_transition(
                opp,
                target_status=transition.status,
                reason=transition.reason,
                metadata_json=transition.metadata_json,
                actor=actor,
                project_id=project_id,
            )
            self._session.commit()
            self._session.refresh(opp)
            return opp
        except Exception:
            self._session.rollback()
            raise

    def update_opportunity(
        self,
        opp_id_or_slug: str,
        data: OpportunityUpdate,
        project_id: str,
        actor: str,
    ) -> GrowthOpportunity:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)

        # If status is changing, enforce full lifecycle transition in the
        # same transaction as the field updates (flush, not commit).
        status_changed = data.status is not None and data.status != opp.status
        if status_changed:
            self._apply_transition(
                opp,
                target_status=data.status,
                reason=data.reason,
                metadata_json=data.metadata_json,
                actor=actor,
                project_id=project_id,
            )

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field in ("status", "reason"):
                continue
            if field == "metadata_json":
                opp.metadata_json = value
            elif hasattr(opp, field):
                setattr(opp, field, value)

        # Recalculate priority if impact or effort changed
        opp.priority = calculate_priority(opp.estimated_impact, opp.estimated_effort)
        opp.updated_at = datetime.now(timezone.utc)

        try:
            self._session.commit()
            self._session.refresh(opp)
            return opp
        except Exception:
            self._session.rollback()
            raise

    def delete_opportunity(self, opp_id_or_slug: str, project_id: str) -> None:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)

        # Integrity correction #1: Reject destructive deletion if audit records exist
        history_count = self._session.scalar(
            select(func.count())
            .select_from(OpportunityStatusHistory)
            .where(OpportunityStatusHistory.opportunity_id == opp.id)
        )
        if history_count and history_count > 0:
            raise ConflictError(
                "Opportunities with audit history cannot be deleted. Archive the opportunity instead to preserve the audit trail.",
                code="cannot_delete_audited_opportunity",
            )

        try:
            self._session.delete(opp)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def get_history(
        self, opp_id_or_slug: str, project_id: str
    ) -> Sequence[OpportunityStatusHistory]:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)
        stmt = (
            select(OpportunityStatusHistory)
            .where(
                (OpportunityStatusHistory.opportunity_id == opp.id)
                & (OpportunityStatusHistory.project_id == project_id)
            )
            .order_by(OpportunityStatusHistory.created_at.asc())
        )
        return self._session.scalars(stmt).all()

    def associate_research(
        self, opp_id_or_slug: str, items: list[AssociationItem], project_id: str
    ) -> list[OpportunityResearchAssociation]:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)

        # Verify all research IDs exist in the same project
        results = []
        for item in items:
            stmt = select(ResearchRecord).where(
                (ResearchRecord.id == item.research_id) & (ResearchRecord.project_id == project_id)
            )
            record = self._session.scalar(stmt)
            if not record:
                raise NotFoundError(
                    f"Research record '{item.research_id}' not found in this project"
                )

            # Upsert association
            assoc_stmt = select(OpportunityResearchAssociation).where(
                (OpportunityResearchAssociation.opportunity_id == opp.id)
                & (OpportunityResearchAssociation.research_id == item.research_id)
            )
            existing_assoc = self._session.scalar(assoc_stmt)
            if existing_assoc:
                existing_assoc.notes = item.notes
                assoc = existing_assoc
            else:
                assoc = OpportunityResearchAssociation(
                    opportunity_id=opp.id,
                    research_id=item.research_id,
                    project_id=project_id,
                    notes=item.notes,
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

    def list_associated_research(
        self, opp_id_or_slug: str, project_id: str
    ) -> list[tuple[OpportunityResearchAssociation, ResearchRecord]]:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)
        stmt = (
            select(OpportunityResearchAssociation, ResearchRecord)
            .join(
                ResearchRecord,
                (OpportunityResearchAssociation.research_id == ResearchRecord.id)
                & (OpportunityResearchAssociation.project_id == ResearchRecord.project_id),
            )
            .where(OpportunityResearchAssociation.opportunity_id == opp.id)
            .order_by(OpportunityResearchAssociation.created_at.desc())
        )
        return list(self._session.execute(stmt).all())

    def unlink_research(
        self, opp_id_or_slug: str, research_id: str, project_id: str
    ) -> None:
        opp = self.get_opportunity(opp_id_or_slug, project_id=project_id)
        stmt = select(OpportunityResearchAssociation).where(
            (OpportunityResearchAssociation.opportunity_id == opp.id)
            & (OpportunityResearchAssociation.research_id == research_id)
        )
        assoc = self._session.scalar(stmt)
        if not assoc:
            raise NotFoundError(
                f"Association between opportunity '{opp_id_or_slug}' and research '{research_id}' not found"
            )

        try:
            self._session.delete(assoc)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
