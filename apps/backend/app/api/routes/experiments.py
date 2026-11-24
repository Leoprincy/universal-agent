"""Phase 7 experiment routes, nested under strategies."""

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_experiment_service,
    get_project_service,
)
from app.schemas.experiment import (
    ExperimentEvaluationResponse,
    ExperimentListResponse,
    ExperimentOutcomeCreate,
    ExperimentOutcomeResponse,
    ExperimentResponse,
    ExperimentStatusHistoryResponse,
    ExperimentTransition,
    ExperimentUpdate,
    ExperimentCreate,
)
from app.services.experiment import ExperimentService
from app.services.project import ProjectService

router = APIRouter()


def _to_experiment_response(e) -> ExperimentResponse:
    return ExperimentResponse.model_validate(e)


def _to_outcome_response(o) -> ExperimentOutcomeResponse:
    return ExperimentOutcomeResponse.model_validate(o)


def _to_evaluation_response(ev) -> ExperimentEvaluationResponse:
    return ExperimentEvaluationResponse.model_validate(ev)


def _to_history_response(h) -> ExperimentStatusHistoryResponse:
    return ExperimentStatusHistoryResponse.model_validate(h)


@router.get(
    "/{strategy_id_or_slug}/experiments",
    response_model=ExperimentListResponse,
    summary="List experiments for a strategy",
)
def list_experiments(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = experiment_service.list_experiments(
        strategy_id_or_slug,
        project_id=project.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ExperimentListResponse(
        items=[_to_experiment_response(e) for e in items], total=total
    )


@router.post(
    "/{strategy_id_or_slug}/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an experiment under a strategy",
)
def create_experiment(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    data: ExperimentCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    exp = experiment_service.create_experiment(
        strategy_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_experiment_response(exp)


@router.get(
    "/{strategy_id_or_slug}/experiments/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Get an experiment",
)
def get_experiment(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    exp = experiment_service.get_experiment(
        experiment_id, strategy_id_or_slug, project_id=project.id
    )
    return _to_experiment_response(exp)


@router.patch(
    "/{strategy_id_or_slug}/experiments/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Update permitted experiment fields (draft only for most fields)",
)
def update_experiment(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    data: ExperimentUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    exp = experiment_service.update_experiment(
        experiment_id, strategy_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_experiment_response(exp)


@router.post(
    "/{strategy_id_or_slug}/experiments/{experiment_id}/transition",
    response_model=ExperimentResponse,
    summary="Transition experiment lifecycle status",
)
def transition_experiment(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    data: ExperimentTransition,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    exp = experiment_service.transition_experiment(
        experiment_id, strategy_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_experiment_response(exp)


@router.get(
    "/{strategy_id_or_slug}/experiments/{experiment_id}/history",
    response_model=list[ExperimentStatusHistoryResponse],
    summary="List experiment status history",
)
def list_experiment_history(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> list[ExperimentStatusHistoryResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items = experiment_service.get_history(
        experiment_id, strategy_id_or_slug, project_id=project.id
    )
    return [_to_history_response(h) for h in items]


@router.post(
    "/{strategy_id_or_slug}/experiments/{experiment_id}/outcomes",
    response_model=ExperimentOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an append-only experiment outcome",
)
def record_outcome(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    data: ExperimentOutcomeCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentOutcomeResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    outcome = experiment_service.record_outcome(
        experiment_id, strategy_id_or_slug, data, project_id=project.id, actor=identity.owner
    )
    return _to_outcome_response(outcome)


@router.get(
    "/{strategy_id_or_slug}/experiments/{experiment_id}/outcomes",
    response_model=list[ExperimentOutcomeResponse],
    summary="List experiment outcomes",
)
def list_outcomes(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    metric_name: str | None = Query(None),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> list[ExperimentOutcomeResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items = experiment_service.list_outcomes(
        experiment_id, strategy_id_or_slug, project_id=project.id, metric_name=metric_name
    )
    return [_to_outcome_response(o) for o in items]


@router.post(
    "/{strategy_id_or_slug}/experiments/{experiment_id}/evaluate",
    response_model=ExperimentEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate experiment against success criteria (append-only)",
)
def evaluate_experiment(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> ExperimentEvaluationResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    evaluation = experiment_service.evaluate(
        experiment_id, strategy_id_or_slug, project_id=project.id, actor=identity.owner
    )
    return _to_evaluation_response(evaluation)


@router.get(
    "/{strategy_id_or_slug}/experiments/{experiment_id}/evaluations",
    response_model=list[ExperimentEvaluationResponse],
    summary="List experiment evaluations (append-only history)",
)
def list_evaluations(
    project_id_or_slug: str,
    strategy_id_or_slug: str,
    experiment_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    experiment_service: ExperimentService = Depends(get_experiment_service),
) -> list[ExperimentEvaluationResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items = experiment_service.list_evaluations(
        experiment_id, strategy_id_or_slug, project_id=project.id
    )
    return [_to_evaluation_response(e) for e in items]
