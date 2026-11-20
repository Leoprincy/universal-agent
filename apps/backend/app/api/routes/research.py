from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_project_service,
    get_research_service,
)
from app.schemas.research import (
    ResearchRecordCreate,
    ResearchRecordListResponse,
    ResearchRecordResponse,
    ResearchRecordUpdate,
    SourceType,
)
from app.services.project import ProjectService
from app.services.research import ResearchService

router = APIRouter()


def _to_research_response(r) -> ResearchRecordResponse:
    return ResearchRecordResponse(
        id=r.id,
        project_id=r.project_id,
        title=r.title,
        source_type=r.source_type,
        source_url=r.source_url,
        source_name=r.source_name,
        author=r.author,
        source_quote=r.source_quote,
        observation_summary=r.observation_summary,
        interpretation_notes=r.interpretation_notes,
        evidence_data=r.evidence_data,
        observed_at=r.observed_at,
        published_at=r.published_at,
        collected_at=r.collected_at,
        metadata=r.metadata_json,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=ResearchRecordListResponse, summary="List research records for a project")
def list_research_records(
    project_id_or_slug: str,
    source_type: SourceType | None = Query(None, description="Filter by source type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    research_service: ResearchService = Depends(get_research_service),
) -> ResearchRecordListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = research_service.list_records(
        project_id=project.id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )
    return ResearchRecordListResponse(
        items=[_to_research_response(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ResearchRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new research record",
)
def create_research_record(
    project_id_or_slug: str,
    data: ResearchRecordCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    research_service: ResearchService = Depends(get_research_service),
) -> ResearchRecordResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    record = research_service.create_record(data, project_id=project.id)
    return _to_research_response(record)


@router.get(
    "/{record_id}",
    response_model=ResearchRecordResponse,
    summary="Get research record by ID",
)
def get_research_record(
    project_id_or_slug: str,
    record_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    research_service: ResearchService = Depends(get_research_service),
) -> ResearchRecordResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    record = research_service.get_record(record_id, project_id=project.id)
    return _to_research_response(record)


@router.patch(
    "/{record_id}",
    response_model=ResearchRecordResponse,
    summary="Update research record",
)
def update_research_record(
    project_id_or_slug: str,
    record_id: str,
    data: ResearchRecordUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    research_service: ResearchService = Depends(get_research_service),
) -> ResearchRecordResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    record = research_service.update_record(record_id, data, project_id=project.id)
    return _to_research_response(record)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete research record",
)
def delete_research_record(
    project_id_or_slug: str,
    record_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    research_service: ResearchService = Depends(get_research_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    research_service.delete_record(record_id, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
