import re
import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.database.models import (
    Experiment,
    ExperimentEvaluation,
    ExperimentOutcome,
    ExperimentStatusHistory,
    GoalMetricUpdate,
    GoalStatusHistory,
    IntegrationAction,
    IntegrationCredential,
    Job,
    JobEvent,
    JobOutboxEvent,
    LearningRecord,
    OpportunityStatusHistory,
    Project,
    StrategyStatusHistory,
)
from app.schemas.project import ProjectCreate, ProjectUpdate


def generate_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    cleaned = cleaned[:140].rstrip("-")
    return cleaned or f"project-{uuid.uuid4().hex[:6]}"


class ProjectService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_projects(
        self,
        status: str | None = None,
        category: str | None = None,
        owner: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Project], int]:
        base_query = select(Project)
        count_query = select(func.count()).select_from(Project)

        if owner:
            base_query = base_query.where(Project.owner == owner)
            count_query = count_query.where(Project.owner == owner)
        if status:
            base_query = base_query.where(Project.status == status)
            count_query = count_query.where(Project.status == status)
        if category:
            base_query = base_query.where(Project.category == category)
            count_query = count_query.where(Project.category == category)

        total = self._session.scalar(count_query) or 0
        items_query = (
            base_query.order_by(Project.created_at.desc(), Project.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = self._session.scalars(items_query).all()
        return items, total

    def get_project(self, project_id_or_slug: str, owner: str | None = None) -> Project:
        stmt = select(Project).where(
            (Project.id == project_id_or_slug) | (Project.slug == project_id_or_slug)
        )
        if owner:
            stmt = stmt.where(Project.owner == owner)
        project = self._session.scalar(stmt)
        if not project:
            raise NotFoundError(f"Project '{project_id_or_slug}' not found")
        return project

    def create_project(self, data: ProjectCreate, owner: str = "default") -> Project:
        slug = data.slug or generate_slug(data.name)
        project_owner = owner
        # Check if slug exists
        existing = self._session.scalar(select(Project).where(Project.slug == slug))
        if existing:
            if data.slug:
                raise ConflictError(f"Project with slug '{slug}' already exists")
            # Auto-suffix slug with a bounded retry limit
            base_slug = slug[:130].rstrip("-")
            counter = 1
            max_attempts = 100
            while existing and counter <= max_attempts:
                slug = f"{base_slug}-{counter}"
                existing = self._session.scalar(select(Project).where(Project.slug == slug))
                counter += 1
            if existing:
                slug = f"{base_slug[:120].rstrip('-')}-{uuid.uuid4().hex[:8]}"

        project = Project(
            id=str(uuid.uuid4()),
            name=data.name,
            slug=slug,
            owner=project_owner,
            description=data.description,
            category=data.category,
            status="active",
            target_audience=data.target_audience,
            metadata_json=data.metadata,
        )
        try:
            self._session.add(project)
            self._session.commit()
            self._session.refresh(project)
            return project
        except IntegrityError as exc:
            self._session.rollback()
            orig_msg = str(getattr(exc, "orig", exc)).lower()
            if "ix_projects_slug" in orig_msg or "projects.slug" in orig_msg or ("unique" in orig_msg and "slug" in orig_msg):
                raise ConflictError(f"Project with slug '{slug}' already exists") from exc
            raise

    def update_project(
        self,
        project_id_or_slug: str,
        data: ProjectUpdate,
        owner: str | None = None,
    ) -> Project:
        project = self.get_project(project_id_or_slug, owner=owner)
        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.category is not None:
            project.category = data.category
        if data.status is not None:
            project.status = data.status
        if data.target_audience is not None:
            project.target_audience = data.target_audience
        if data.metadata is not None:
            project.metadata_json = data.metadata

        try:
            self._session.commit()
            self._session.refresh(project)
            return project
        except IntegrityError as exc:
            self._session.rollback()
            orig_msg = str(getattr(exc, "orig", exc)).lower()
            if "ix_projects_slug" in orig_msg or "projects.slug" in orig_msg or ("unique" in orig_msg and "slug" in orig_msg):
                raise ConflictError(f"Project with slug '{project.slug}' already exists") from exc
            raise

    def delete_project(self, project_id_or_slug: str, owner: str | None = None) -> None:
        project = self.get_project(project_id_or_slug, owner=owner)

        # Pre-deletion audit guard: history tables use ON DELETE RESTRICT,
        # so any audited child records would fail the delete with an opaque
        # integrity error. Check explicitly and explain instead.
        blockers: list[str] = []
        opp_history = self._session.scalar(
            select(func.count())
            .select_from(OpportunityStatusHistory)
            .where(OpportunityStatusHistory.project_id == project.id)
        ) or 0
        if opp_history:
            blockers.append(f"{opp_history} opportunity status transition(s)")
        strat_history = self._session.scalar(
            select(func.count())
            .select_from(StrategyStatusHistory)
            .where(StrategyStatusHistory.project_id == project.id)
        ) or 0
        if strat_history:
            blockers.append(f"{strat_history} strategy status transition(s)")
        goal_metric = self._session.scalar(
            select(func.count())
            .select_from(GoalMetricUpdate)
            .where(GoalMetricUpdate.project_id == project.id)
        ) or 0
        if goal_metric:
            blockers.append(f"{goal_metric} goal metric update(s)")
        goal_status = self._session.scalar(
            select(func.count())
            .select_from(GoalStatusHistory)
            .where(GoalStatusHistory.project_id == project.id)
        ) or 0
        if goal_status:
            blockers.append(f"{goal_status} goal status transition(s)")
        integration_actions = self._session.scalar(
            select(func.count())
            .select_from(IntegrationAction)
            .where(IntegrationAction.project_id == project.id)
        ) or 0
        if integration_actions:
            blockers.append(f"{integration_actions} integration action(s)")
        integration_credentials = self._session.scalar(
            select(func.count())
            .select_from(IntegrationCredential)
            .where(IntegrationCredential.project_id == project.id)
        ) or 0
        if integration_credentials:
            blockers.append(f"{integration_credentials} integration credential(s)")
        experiments = self._session.scalar(
            select(func.count())
            .select_from(Experiment)
            .where(Experiment.project_id == project.id)
        ) or 0
        if experiments:
            blockers.append(f"{experiments} experiment(s)")
        exp_history = self._session.scalar(
            select(func.count())
            .select_from(ExperimentStatusHistory)
            .where(ExperimentStatusHistory.project_id == project.id)
        ) or 0
        if exp_history:
            blockers.append(f"{exp_history} experiment status transition(s)")
        exp_outcomes = self._session.scalar(
            select(func.count())
            .select_from(ExperimentOutcome)
            .where(ExperimentOutcome.project_id == project.id)
        ) or 0
        if exp_outcomes:
            blockers.append(f"{exp_outcomes} experiment outcome(s)")
        exp_evals = self._session.scalar(
            select(func.count())
            .select_from(ExperimentEvaluation)
            .where(ExperimentEvaluation.project_id == project.id)
        ) or 0
        if exp_evals:
            blockers.append(f"{exp_evals} experiment evaluation(s)")
        learnings = self._session.scalar(
            select(func.count())
            .select_from(LearningRecord)
            .where(LearningRecord.project_id == project.id)
        ) or 0
        if learnings:
            blockers.append(f"{learnings} learning record(s)")
        jobs = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.project_id == project.id)
        ) or 0
        if jobs:
            blockers.append(f"{jobs} job(s)")
        job_events = self._session.scalar(
            select(func.count())
            .select_from(JobEvent)
            .where(JobEvent.project_id == project.id)
        ) or 0
        if job_events:
            blockers.append(f"{job_events} job lifecycle event(s)")
        job_outbox = self._session.scalar(
            select(func.count())
            .select_from(JobOutboxEvent)
            .where(JobOutboxEvent.project_id == project.id)
        ) or 0
        if job_outbox:
            blockers.append(f"{job_outbox} job dispatch outbox record(s)")

        if blockers:
            raise ConflictError(
                "Project cannot be deleted because it contains audited records: "
                + ", ".join(blockers)
                + ". Archive the project instead to preserve the audit trail.",
                code="cannot_delete_audited_project",
            )

        try:
            self._session.delete(project)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
