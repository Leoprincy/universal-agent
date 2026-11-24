"""Phase 7 project-scoped learning record routes."""

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_learning_service,
    get_project_service,
)
from app.schemas.learning import (
    LearningCreate,
    LearningListResponse,
    LearningReject,
    LearningResponse,
    LearningUpdate,
)
from app.services.learning import LearningService
from app.services.project import ProjectService

router = APIRouter()


def _to_response(r) -> LearningResponse:
    return LearningResponse.model_validate(r)


@router.get(
    "/validated",
    response_model=LearningListResponse,
    summary="Validated learnings for recommendation workflows",
)
def list_validated_learnings(
    project_id_or_slug: str,
    strategy_id: str | None = Query(None),
    experiment_id: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = learning_service.get_validated(
        project.id,
        strategy_id=strategy_id,
        experiment_id=experiment_id,
        category=category,
        limit=limit,
        offset=offset,
    )
    return LearningListResponse(items=[_to_response(r) for r in items], total=total)


@router.get("", response_model=LearningListResponse, summary="List learning records")
def list_learnings(
    project_id_or_slug: str,
    strategy_id: str | None = Query(None),
    experiment_id: str | None = Query(None),
    category: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = learning_service.list(
        project.id,
        strategy_id=strategy_id,
        experiment_id=experiment_id,
        category=category,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return LearningListResponse(items=[_to_response(r) for r in items], total=total)


@router.post(
    "",
    response_model=LearningResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a candidate learning record",
)
def create_learning(
    project_id_or_slug: str,
    data: LearningCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    rec = learning_service.create(data, project_id=project.id, actor=identity.owner)
    return _to_response(rec)


@router.get("/{learning_id}", response_model=LearningResponse, summary="Get a learning record")
def get_learning(
    project_id_or_slug: str,
    learning_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    rec = learning_service.get(learning_id, project_id=project.id)
    return _to_response(rec)


@router.patch(
    "/{learning_id}",
    response_model=LearningResponse,
    summary="Update a candidate learning record",
)
def update_learning(
    project_id_or_slug: str,
    learning_id: str,
    data: LearningUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    rec = learning_service.update(learning_id, data, project_id=project.id, actor=identity.owner)
    return _to_response(rec)


@router.post(
    "/{learning_id}/validate",
    response_model=LearningResponse,
    summary="Validate a candidate learning record",
)
def validate_learning(
    project_id_or_slug: str,
    learning_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    rec = learning_service.validate(learning_id, project_id=project.id, actor=identity.owner)
    return _to_response(rec)


@router.post(
    "/{learning_id}/reject",
    response_model=LearningResponse,
    summary="Reject a candidate learning record",
)
def reject_learning(
    project_id_or_slug: str,
    learning_id: str,
    data: LearningReject,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    learning_service: LearningService = Depends(get_learning_service),
) -> LearningResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    rec = learning_service.reject(
        learning_id, data.reason, project_id=project.id, actor=identity.owner
    )
    return _to_response(rec)
