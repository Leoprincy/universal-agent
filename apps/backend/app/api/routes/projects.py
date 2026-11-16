from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import AuthIdentity, get_current_identity, get_project_service
from app.schemas.project import (
    ProjectCategory,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectStatus,
    ProjectUpdate,
)
from app.services.project import ProjectService

router = APIRouter()


def _to_response(project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        slug=project.slug,
        owner=getattr(project, "owner", "default"),
        description=project.description,
        category=project.category,
        status=project.status,
        target_audience=project.target_audience,
        metadata=project.metadata_json,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=ProjectListResponse, summary="List growth projects")
def list_projects(
    status: ProjectStatus | None = Query(None, description="Filter by status"),
    category: ProjectCategory | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    identity: AuthIdentity = Depends(get_current_identity),
    service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    items, total = service.list_projects(
        status=status,
        category=category,
        owner=identity.owner,
        limit=limit,
        offset=offset,
    )
    return ProjectListResponse(
        items=[_to_response(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new growth project",
)
def create_project(
    data: ProjectCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = service.create_project(data, owner=identity.owner)
    return _to_response(project)


@router.get(
    "/{project_id_or_slug}",
    response_model=ProjectResponse,
    summary="Get project by ID or slug",
)
def get_project(
    project_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = service.get_project(project_id_or_slug, owner=identity.owner)
    return _to_response(project)


@router.patch(
    "/{project_id_or_slug}",
    response_model=ProjectResponse,
    summary="Update project details",
)
def update_project(
    project_id_or_slug: str,
    data: ProjectUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = service.update_project(project_id_or_slug, data, owner=identity.owner)
    return _to_response(project)


@router.delete(
    "/{project_id_or_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a growth project",
)
def delete_project(
    project_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    service: ProjectService = Depends(get_project_service),
) -> Response:
    service.delete_project(project_id_or_slug, owner=identity.owner)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
