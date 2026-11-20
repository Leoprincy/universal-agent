from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_opportunity_service,
    get_project_service,
)
from app.api.routes.research import _to_research_response
from app.schemas.association import (
    AssociateResearchRequest,
    AssociateResearchResponse,
    AssociatedResearchResponse,
)
from app.schemas.history import (
    OpportunityStatusHistoryListResponse,
    OpportunityStatusHistoryResponse,
)
from app.schemas.opportunity import (
    OpportunityCategory,
    OpportunityCreate,
    OpportunityListResponse,
    OpportunityPriority,
    OpportunityResponse,
    OpportunityStatus,
    OpportunityTransition,
    OpportunityUpdate,
)
from app.services.opportunity import OpportunityService
from app.services.project import ProjectService

router = APIRouter()


def _to_opportunity_response(o) -> OpportunityResponse:
    return OpportunityResponse(
        id=o.id,
        project_id=o.project_id,
        title=o.title,
        slug=o.slug,
        problem_statement=o.problem_statement,
        hypothesis=o.hypothesis,
        proposed_mechanism=o.proposed_mechanism,
        target_audience=o.target_audience,
        category=o.category,
        status=o.status,
        estimated_impact=o.estimated_impact,
        estimated_effort=o.estimated_effort,
        confidence_score=float(o.confidence_score) if o.confidence_score is not None else None,
        priority=o.priority,
        metadata=o.metadata_json,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def _to_history_response(h) -> OpportunityStatusHistoryResponse:
    return OpportunityStatusHistoryResponse(
        id=h.id,
        opportunity_id=h.opportunity_id,
        project_id=h.project_id,
        previous_status=h.previous_status,
        new_status=h.new_status,
        reason=h.reason,
        actor=h.actor,
        system_metadata=h.system_metadata_json,
        created_at=h.created_at,
    )


@router.get("", response_model=OpportunityListResponse, summary="List growth opportunities for a project")
def list_opportunities(
    project_id_or_slug: str,
    status: OpportunityStatus | None = Query(None, description="Filter by status"),
    category: OpportunityCategory | None = Query(None, description="Filter by category"),
    priority: OpportunityPriority | None = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = opportunity_service.list_opportunities(
        project_id=project.id,
        status=status,
        category=category,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return OpportunityListResponse(
        items=[_to_opportunity_response(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=OpportunityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new growth opportunity",
)
def create_opportunity(
    project_id_or_slug: str,
    data: OpportunityCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    opp = opportunity_service.create_opportunity(data, project_id=project.id, actor=identity.owner)
    return _to_opportunity_response(opp)


@router.get(
    "/{opp_id_or_slug}",
    response_model=OpportunityResponse,
    summary="Get growth opportunity by ID or slug",
)
def get_opportunity(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    opp = opportunity_service.get_opportunity(opp_id_or_slug, project_id=project.id)
    return _to_opportunity_response(opp)


@router.patch(
    "/{opp_id_or_slug}",
    response_model=OpportunityResponse,
    summary="Update growth opportunity",
)
def update_opportunity(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    data: OpportunityUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    opp = opportunity_service.update_opportunity(
        opp_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_opportunity_response(opp)


@router.delete(
    "/{opp_id_or_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete growth opportunity",
)
def delete_opportunity(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    opportunity_service.delete_opportunity(opp_id_or_slug, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{opp_id_or_slug}/transition",
    response_model=OpportunityResponse,
    summary="Execute status lifecycle transition",
)
def transition_opportunity(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    data: OpportunityTransition,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    opp = opportunity_service.transition_opportunity(
        opp_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_opportunity_response(opp)


@router.get(
    "/{opp_id_or_slug}/history",
    response_model=OpportunityStatusHistoryListResponse,
    summary="Get status history timeline for an opportunity",
)
def get_opportunity_history(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> OpportunityStatusHistoryListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    history = opportunity_service.get_history(opp_id_or_slug, project_id=project.id)
    return OpportunityStatusHistoryListResponse(
        items=[_to_history_response(h) for h in history],
        total=len(history),
    )


@router.post(
    "/{opp_id_or_slug}/research",
    response_model=AssociateResearchResponse,
    summary="Associate research records with an opportunity",
)
def associate_research(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    data: AssociateResearchRequest,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> AssociateResearchResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    assocs = opportunity_service.associate_research(opp_id_or_slug, data.items, project_id=project.id)
    items = [
        AssociatedResearchResponse(
            research_id=a.research_id,
            opportunity_id=a.opportunity_id,
            project_id=a.project_id,
            notes=a.notes,
            created_at=a.created_at,
        )
        for a in assocs
    ]
    return AssociateResearchResponse(linked_count=len(items), items=items)


@router.get(
    "/{opp_id_or_slug}/research",
    response_model=list[AssociatedResearchResponse],
    summary="List research records linked to an opportunity",
)
def list_associated_research(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> list[AssociatedResearchResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    pairs = opportunity_service.list_associated_research(opp_id_or_slug, project_id=project.id)
    return [
        AssociatedResearchResponse(
            research_id=assoc.research_id,
            opportunity_id=assoc.opportunity_id,
            project_id=assoc.project_id,
            notes=assoc.notes,
            created_at=assoc.created_at,
            research=_to_research_response(rec) if rec else None,
        )
        for assoc, rec in pairs
    ]


@router.delete(
    "/{opp_id_or_slug}/research/{research_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink research record from an opportunity",
)
def unlink_research(
    project_id_or_slug: str,
    opp_id_or_slug: str,
    research_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    opportunity_service: OpportunityService = Depends(get_opportunity_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    opportunity_service.unlink_research(opp_id_or_slug, research_id, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
