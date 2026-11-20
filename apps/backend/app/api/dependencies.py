from dataclasses import dataclass
from typing import Generator
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.database.connection import DatabaseConnection
from app.services.health import HealthService
from app.services.opportunity import OpportunityService
from app.services.project import ProjectService
from app.services.research import ResearchService


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
    return HealthService(database=request.app.state.database, redis=request.app.state.redis)


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
