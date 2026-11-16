import re
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.database.models import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


def generate_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return cleaned or f"project-{uuid.uuid4().hex[:6]}"


class ProjectService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_projects(
        self,
        status: str | None = None,
        category: str | None = None,
    ) -> Sequence[Project]:
        query = select(Project).order_by(Project.created_at.desc())
        if status:
            query = query.where(Project.status == status)
        if category:
            query = query.where(Project.category == category)
        return self._session.scalars(query).all()

    def get_project(self, project_id_or_slug: str) -> Project:
        stmt = select(Project).where(
            (Project.id == project_id_or_slug) | (Project.slug == project_id_or_slug)
        )
        project = self._session.scalar(stmt)
        if not project:
            raise NotFoundError(f"Project '{project_id_or_slug}' not found")
        return project

    def create_project(self, data: ProjectCreate) -> Project:
        slug = data.slug or generate_slug(data.name)
        # Check if slug exists
        existing = self._session.scalar(select(Project).where(Project.slug == slug))
        if existing:
            if data.slug:
                raise ConflictError(f"Project with slug '{slug}' already exists")
            # Auto-suffix slug
            base_slug = slug
            counter = 1
            while existing:
                slug = f"{base_slug}-{counter}"
                existing = self._session.scalar(select(Project).where(Project.slug == slug))
                counter += 1

        project = Project(
            id=str(uuid.uuid4()),
            name=data.name,
            slug=slug,
            description=data.description,
            category=data.category,
            status="active",
            target_audience=data.target_audience,
            metadata_json=data.metadata,
        )
        self._session.add(project)
        self._session.commit()
        self._session.refresh(project)
        return project

    def update_project(self, project_id_or_slug: str, data: ProjectUpdate) -> Project:
        project = self.get_project(project_id_or_slug)
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

        self._session.commit()
        self._session.refresh(project)
        return project

    def delete_project(self, project_id_or_slug: str) -> None:
        project = self.get_project(project_id_or_slug)
        self._session.delete(project)
        self._session.commit()
