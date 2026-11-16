import re
import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.database.models import Project
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
        project_owner = data.owner or owner
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
        try:
            self._session.delete(project)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
