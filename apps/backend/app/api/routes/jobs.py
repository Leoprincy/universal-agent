"""Phase 8 project-scoped job routes."""

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_db_session,
    get_job_queue,
    get_job_service,
    get_project_service,
)
from app.jobs.queue import JobQueue
from app.schemas.job import (
    JobCreate,
    JobEventResponse,
    JobListResponse,
    JobResponse,
    JobScheduleCreate,
    JobScheduleListResponse,
    JobScheduleResponse,
    JobScheduleToggle,
    JobStatsResponse,
)
from app.services.job import JobScheduleService, JobService
from app.services.project import ProjectService

router = APIRouter()


def _to_job(j) -> JobResponse:
    return JobResponse.model_validate(j)


@router.get("", response_model=JobListResponse, summary="List jobs for a project")
def list_jobs(
    project_id_or_slug: str,
    status_filter: str | None = Query(None, alias="status"),
    job_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> JobListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = job_service.list_jobs(
        project.id,
        status=status_filter,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        items=[_to_job(j) for j in items], total=total, limit=limit, offset=offset
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a persistent job",
)
def create_job(
    project_id_or_slug: str,
    data: JobCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    job = job_service.create_job(data, project_id=project.id, actor=identity.owner)
    return _to_job(job)


def _to_schedule(s) -> JobScheduleResponse:
    return JobScheduleResponse(
        id=s.id,
        project_id=s.project_id,
        name=s.name,
        job_type=s.job_type,
        payload=s.payload_json,
        interval_seconds=s.interval_seconds,
        next_run_at=s.next_run_at,
        last_run_at=s.last_run_at,
        enabled=s.enabled,
        created_by=s.created_by,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def get_schedule_service(
    session=Depends(get_db_session),
) -> JobScheduleService:
    return JobScheduleService(session)


@router.get(
    "/schedules",
    response_model=JobScheduleListResponse,
    summary="List recurring job schedules",
)
def list_schedules(
    project_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    schedule_service: JobScheduleService = Depends(get_schedule_service),
) -> JobScheduleListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items = schedule_service.list_schedules(project.id)
    return JobScheduleListResponse(
        items=[_to_schedule(s) for s in items], total=len(items)
    )


@router.post(
    "/schedules",
    response_model=JobScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recurring job schedule",
)
def create_schedule(
    project_id_or_slug: str,
    data: JobScheduleCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    schedule_service: JobScheduleService = Depends(get_schedule_service),
) -> JobScheduleResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    from datetime import datetime, timezone

    next_run = data.next_run_at or datetime.now(timezone.utc)
    schedule = schedule_service.create_schedule(
        project_id=project.id,
        name=data.name,
        job_type=data.job_type,
        payload=data.payload,
        interval_seconds=data.interval_seconds,
        next_run_at=next_run,
        actor=identity.owner,
    )
    return _to_schedule(schedule)


@router.post(
    "/schedules/{schedule_id}/enabled",
    response_model=JobScheduleResponse,
    summary="Enable or disable a recurring schedule",
)
def set_schedule_enabled(
    project_id_or_slug: str,
    schedule_id: str,
    data: JobScheduleToggle,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    schedule_service: JobScheduleService = Depends(get_schedule_service),
) -> JobScheduleResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    schedule = schedule_service.set_enabled(
        schedule_id, project.id, data.enabled, actor=identity.owner
    )
    return _to_schedule(schedule)


@router.get(
    "/stats",
    response_model=JobStatsResponse,
    summary="Job statistics for a project",
)
def job_stats(
    project_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> JobStatsResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return JobStatsResponse.model_validate(job_service.job_stats(project.id))


@router.get("/{job_id}", response_model=JobResponse, summary="Get a job")
def get_job(
    project_id_or_slug: str,
    job_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return _to_job(job_service.get_job(job_id, project_id=project.id))


@router.post(
    "/{job_id}/enqueue",
    response_model=JobResponse,
    summary="Push a pending job onto the queue",
)
async def enqueue_job(
    project_id_or_slug: str,
    job_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    job = await job_service.enqueue_job(job_id, project.id, actor=identity.owner)
    return _to_job(job)


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel an eligible job",
)
def cancel_job(
    project_id_or_slug: str,
    job_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return _to_job(job_service.cancel_job(job_id, project.id, actor=identity.owner))


@router.get(
    "/{job_id}/events",
    response_model=list[JobEventResponse],
    summary="Job lifecycle audit history",
)
def get_job_events(
    project_id_or_slug: str,
    job_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    job_service: JobService = Depends(get_job_service),
) -> list[JobEventResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return [JobEventResponse.model_validate(e) for e in job_service.get_events(job_id, project.id)]
