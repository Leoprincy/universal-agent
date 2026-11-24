"""Phase 8 operational monitoring routes (read-only, admin scope)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_db_session,
    get_job_queue,
)
from app.jobs.queue import JobQueue
from app.schemas.ops import OpsOverviewResponse
from app.services.ops import OpsService

router = APIRouter()


def get_ops_service(
    session: Session = Depends(get_db_session),
    queue: JobQueue = Depends(get_job_queue),
    request: Request = None,
) -> OpsService:
    redis_conn = getattr(request.app.state, "redis", None) if request else None
    redis_client = redis_conn.client if redis_conn is not None else None
    return OpsService(session, queue, redis_client)


@router.get(
    "/ops/overview",
    response_model=OpsOverviewResponse,
    summary="Worker, queue, outbox and job operational overview",
)
async def ops_overview(
    identity: AuthIdentity = Depends(get_current_identity),
    ops: OpsService = Depends(get_ops_service),
) -> OpsOverviewResponse:
    return OpsOverviewResponse.model_validate(await ops.overview())
