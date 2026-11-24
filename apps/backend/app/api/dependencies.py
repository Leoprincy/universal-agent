from dataclasses import dataclass
from typing import Generator
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.database.connection import DatabaseConnection
from app.integrations.codec import CredentialCodec, CredentialConfigError
from app.jobs.queue import QueueHealthCheck, RedisJobQueue, UnavailableJobQueue
from app.services.job import JobService
from app.services.experiment import ExperimentService
from app.services.goal import GoalService
from app.services.health import HealthService
from app.services.opportunity import OpportunityService
from app.services.project import ProjectService
from app.services.research import ResearchService
from app.services.integration import IntegrationService
from app.services.learning import LearningService
from app.services.strategy import StrategyService


@dataclass
class AuthIdentity:
    owner: str = "default"
    authenticated: bool = False


def get_current_identity(
    request: Request,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> AuthIdentity:
    settings = request.app.state.settings
    configured_key = settings.api_key.get_secret_value() if settings.api_key else None

    if configured_key:
        provided_key = None
        if authorization and authorization.lower().startswith("bearer "):
            provided_key = authorization[7:].strip()
        elif x_api_key:
            provided_key = x_api_key.strip()

        if not provided_key or provided_key != configured_key:
            raise UnauthorizedError("Invalid or missing API key")

        return AuthIdentity(owner=settings.workspace_owner, authenticated=True)

    return AuthIdentity(owner=settings.workspace_owner, authenticated=False)


def get_health_service(request: Request) -> HealthService:
    client = request.app.state.redis.client
    queue_check = (
        QueueHealthCheck(RedisJobQueue(client)) if client is not None else None
    )
    return HealthService(
        database=request.app.state.database,
        redis=request.app.state.redis,
        queue=queue_check,
    )


def get_db_session(request: Request) -> Generator[Session, None, None]:
    database: DatabaseConnection = request.app.state.database
    session = database.get_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_project_service(session: Session = Depends(get_db_session)) -> ProjectService:
    return ProjectService(session)


def get_research_service(session: Session = Depends(get_db_session)) -> ResearchService:
    return ResearchService(session)


def get_opportunity_service(session: Session = Depends(get_db_session)) -> OpportunityService:
    return OpportunityService(session)


def get_strategy_service(session: Session = Depends(get_db_session)) -> StrategyService:
    return StrategyService(session)


def get_goal_service(session: Session = Depends(get_db_session)) -> GoalService:
    return GoalService(session)


def get_experiment_service(session: Session = Depends(get_db_session)) -> ExperimentService:
    return ExperimentService(session)


def get_learning_service(session: Session = Depends(get_db_session)) -> LearningService:
    return LearningService(session)


def get_job_queue(request: Request):
    client = request.app.state.redis.client
    if client is None:
        return UnavailableJobQueue()
    return RedisJobQueue(client)


def get_job_service(
    session: Session = Depends(get_db_session),
    queue=Depends(get_job_queue),
) -> JobService:
    return JobService(session, queue=queue)


def get_integration_service(request: Request, session: Session = Depends(get_db_session)) -> IntegrationService:
    settings = request.app.state.settings
    codec = None
    key = settings.credential_encryption_key
    if key is not None:
        try:
            codec = CredentialCodec(key.get_secret_value())
        except CredentialConfigError:
            codec = None
    return IntegrationService(
        session,
        credential_codec=codec,
        approval_ttl_seconds=settings.approval_ttl_seconds,
    )
