from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_goal_service,
    get_project_service,
    get_strategy_service,
)
from app.api.routes.opportunities import _to_opportunity_response
from app.schemas.goal import (
    GoalMetricUpdateCreate,
    GoalMetricUpdateResponse,
    GoalStatus,
    GoalStatusHistoryListResponse,
    GoalStatusHistoryResponse,
    StrategyGoalCreate,
    StrategyGoalResponse,
    StrategyGoalUpdate,
    compute_goal_progress,
)
from app.schemas.strategy import (
    GrowthStrategyCreate,
    GrowthStrategyListResponse,
    GrowthStrategyResponse,
    GrowthStrategyTransition,
    GrowthStrategyUpdate,
    StrategyStatus,
)
from app.schemas.strategy_association import (
    AssociatedOpportunityItem,
    StrategyOpportunityAssociateItem,
    StrategyOpportunityAssociateRequest,
    StrategyOpportunityAssociationResponse,
)
from app.schemas.strategy_history import (
    StrategyStatusHistoryListResponse,
    StrategyStatusHistoryResponse,
)
from app.services.goal import GoalService
from app.services.project import ProjectService
from app.services.strategy import StrategyService

router = APIRouter()


def _to_strategy_response(s) -> GrowthStrategyResponse:
    return GrowthStrategyResponse(
        id=s.id,
        project_id=s.project_id,
        name=s.name,
        slug=s.slug,
        description=s.description,
        strategic_vision=s.strategic_vision,
        target_audience=s.target_audience,
        strategic_constraints=s.strategic_constraints,
        budget_envelope=float(s.budget_envelope) if s.budget_envelope is not None else None,
        currency=s.currency,
        time_horizon=s.time_horizon,
        status=s.status,
        metadata=s.metadata_json,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _to_goal_response(g) -> StrategyGoalResponse:
    baseline = float(g.baseline_value)
    target = float(g.target_value)
    current = float(g.current_value)
    progress_pct, is_increasing = compute_goal_progress(baseline, target, current)
    return StrategyGoalResponse(
        id=g.id,
        project_id=g.project_id,
        strategy_id=g.strategy_id,
        name=g.name,
        description=g.description,
        metric_name=g.metric_name,
        metric_unit=g.metric_unit,
        baseline_value=baseline,
        current_value=current,
        target_value=target,
        deadline=g.deadline,
        status=g.status,
        progress_percentage=progress_pct,
        is_increasing_metric=is_increasing,
        metadata=g.metadata_json,
        created_at=g.created_at,
        updated_at=g.updated_at,
    )


def _to_history_response(h) -> StrategyStatusHistoryResponse:
    return StrategyStatusHistoryResponse(
        id=h.id,
        strategy_id=h.strategy_id,
        project_id=h.project_id,
        previous_status=h.previous_status,
        new_status=h.new_status,
        reason=h.reason,
        actor=h.actor,
        system_metadata=h.system_metadata_json,
        created_at=h.created_at,
    )


def _to_metric_update_response(u) -> GoalMetricUpdateResponse:
    return GoalMetricUpdateResponse(
        id=u.id,
        goal_id=u.goal_id,
        project_id=u.project_id,
        previous_value=float(u.previous_value),
        new_value=float(u.new_value),
        notes=u.notes,
        actor=u.actor,
        created_at=u.created_at,
    )


def _to_goal_history_response(h) -> GoalStatusHistoryResponse:
    return GoalStatusHistoryResponse(
        id=h.id,
        goal_id=h.goal_id,
        project_id=h.project_id,
        previous_status=h.previous_status,
        new_status=h.new_status,
        reason=h.reason,
        actor=h.actor,
        system_metadata=h.system_metadata_json,
        created_at=h.created_at,
    )


# -----------------------------------------------------------------------------
# Strategy Endpoints
# -----------------------------------------------------------------------------


@router.get("", response_model=GrowthStrategyListResponse, summary="List growth strategies for a project")
def list_strategies(
    project_id_or_slug: str,
    status: StrategyStatus | None = Query(None, description="Filter by status"),
    time_horizon: str | None = Query(None, description="Filter by time horizon"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> GrowthStrategyListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = strategy_service.list_strategies(
        project_id=project.id,
        status=status,
        time_horizon=time_horizon,
        limit=limit,
        offset=offset,
    )
    return GrowthStrategyListResponse(
        items=[_to_strategy_response(s) for s in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=GrowthStrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new growth strategy",
)
def create_strategy(
    project_id_or_slug: str,
    data: GrowthStrategyCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> GrowthStrategyResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = strategy_service.create_strategy(data, project_id=project.id, actor=identity.owner)
    return _to_strategy_response(strategy)


@router.get(
    "/{strategy_id_or_slug}",
    response_model=GrowthStrategyResponse,
    summary="Get growth strategy by ID or slug",
)
def get_strategy(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> GrowthStrategyResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = strategy_service.get_strategy(strategy_id_or_slug, project_id=project.id)
    return _to_strategy_response(strategy)


@router.patch(
    "/{strategy_id_or_slug}",
    response_model=GrowthStrategyResponse,
    summary="Update growth strategy (non-status fields only)",
)
def update_strategy(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    data: GrowthStrategyUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> GrowthStrategyResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = strategy_service.update_strategy(
        strategy_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_strategy_response(strategy)


@router.delete(
    "/{strategy_id_or_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete draft growth strategy",
)
def delete_strategy(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy_service.delete_strategy(strategy_id_or_slug, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{strategy_id_or_slug}/transition",
    response_model=GrowthStrategyResponse,
    summary="Execute strategy lifecycle transition",
)
def transition_strategy(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    data: GrowthStrategyTransition,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> GrowthStrategyResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = strategy_service.transition_strategy(
        strategy_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_strategy_response(strategy)


@router.get(
    "/{strategy_id_or_slug}/history",
    response_model=StrategyStatusHistoryListResponse,
    summary="Get status history timeline for a strategy",
)
def get_strategy_history(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> StrategyStatusHistoryListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    history = strategy_service.get_history(strategy_id_or_slug, project_id=project.id)
    return StrategyStatusHistoryListResponse(
        items=[_to_history_response(h) for h in history],
        total=len(history),
    )


# -----------------------------------------------------------------------------
# Strategic Goals Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/{strategy_id_or_slug}/goals",
    response_model=list[StrategyGoalResponse],
    summary="List measurable goals for a strategy",
)
def list_goals(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    status: GoalStatus | None = Query(None, description="Filter by goal status"),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> list[StrategyGoalResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    goals = goal_service.list_goals(strategy_id_or_slug, project_id=project.id, status=status)
    return [_to_goal_response(g) for g in goals]


@router.post(
    "/{strategy_id_or_slug}/goals",
    response_model=StrategyGoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new measurable goal for a strategy",
)
def create_goal(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    data: StrategyGoalCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> StrategyGoalResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    goal = goal_service.create_goal(
        strategy.id, data, project_id=project.id, actor=identity.owner
    )
    return _to_goal_response(goal)


@router.get(
    "/{strategy_id_or_slug}/goals/{goal_id}",
    response_model=StrategyGoalResponse,
    summary="Get goal by ID",
)
def get_goal(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    goal_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> StrategyGoalResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    goal = goal_service.get_goal(goal_id, strategy.id, project_id=project.id)
    return _to_goal_response(goal)


@router.patch(
    "/{strategy_id_or_slug}/goals/{goal_id}",
    response_model=StrategyGoalResponse,
    summary="Update goal details",
)
def update_goal(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    goal_id: str,
    data: StrategyGoalUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> StrategyGoalResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    goal = goal_service.update_goal(
        goal_id, strategy.id, data, project_id=project.id, actor=identity.owner
    )
    return _to_goal_response(goal)


@router.delete(
    "/{strategy_id_or_slug}/goals/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete goal (prohibited if metric history exists)",
)
def delete_goal(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    goal_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    goal_service.delete_goal(goal_id, strategy.id, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{strategy_id_or_slug}/goals/{goal_id}/progress",
    response_model=GoalMetricUpdateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record progress check-in for a goal",
)
def record_goal_progress(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    goal_id: str,
    data: GoalMetricUpdateCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> GoalMetricUpdateResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    _, metric_record = goal_service.record_progress(
        goal_id, strategy.id, data, project_id=project.id, actor=identity.owner
    )
    return _to_metric_update_response(metric_record)


@router.get(
    "/{strategy_id_or_slug}/goals/{goal_id}/progress",
    response_model=list[GoalMetricUpdateResponse],
    summary="Get metric check-in history for a goal",
)
def get_goal_metric_history(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    goal_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> list[GoalMetricUpdateResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    updates = goal_service.get_metric_history(goal_id, strategy.id, project_id=project.id)
    return [_to_metric_update_response(u) for u in updates]


@router.get(
    "/{strategy_id_or_slug}/goals/{goal_id}/history",
    response_model=GoalStatusHistoryListResponse,
    summary="Get status history timeline for a goal",
)
def get_goal_status_history(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    goal_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    goal_service: GoalService = Depends(get_goal_service),
) -> GoalStatusHistoryListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy = goal_service._resolve_strategy(strategy_id_or_slug, project_id=project.id)
    history = goal_service.get_status_history(goal_id, strategy.id, project_id=project.id)
    return GoalStatusHistoryListResponse(
        items=[_to_goal_history_response(h) for h in history],
        total=len(history),
    )


# -----------------------------------------------------------------------------
# Opportunity Association Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/{strategy_id_or_slug}/opportunities",
    response_model=list[AssociatedOpportunityItem],
    summary="List opportunities linked to a strategy",
)
def list_associated_opportunities(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> list[AssociatedOpportunityItem]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    pairs = strategy_service.list_associated_opportunities(strategy_id_or_slug, project_id=project.id)
    return [
        AssociatedOpportunityItem(
            strategy_id=assoc.strategy_id,
            opportunity_id=assoc.opportunity_id,
            project_id=assoc.project_id,
            strategic_rationale=assoc.strategic_rationale,
            created_at=assoc.created_at,
            opportunity=_to_opportunity_response(opp),
        )
        for assoc, opp in pairs
    ]


@router.post(
    "/{strategy_id_or_slug}/opportunities",
    response_model=list[StrategyOpportunityAssociationResponse],
    summary="Associate opportunities with a strategy",
)
def associate_opportunities(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    data: StrategyOpportunityAssociateRequest | list[StrategyOpportunityAssociateItem],
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> list[StrategyOpportunityAssociationResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items = data.items if isinstance(data, StrategyOpportunityAssociateRequest) else data
    results = strategy_service.associate_opportunities(
        strategy_id_or_slug, items=items, project_id=project.id
    )
    return [
        StrategyOpportunityAssociationResponse(
            strategy_id=r.strategy_id,
            opportunity_id=r.opportunity_id,
            project_id=r.project_id,
            strategic_rationale=r.strategic_rationale,
            created_at=r.created_at,
        )
        for r in results
    ]


@router.delete(
    "/{strategy_id_or_slug}/opportunities/{opportunity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink an opportunity from a strategy",
)
def unlink_opportunity(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    opportunity_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    strategy_service.unlink_opportunity(
        strategy_id_or_slug, opportunity_id=opportunity_id, project_id=project.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
