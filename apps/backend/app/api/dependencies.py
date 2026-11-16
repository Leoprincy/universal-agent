from typing import Generator
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.connection import DatabaseConnection
from app.services.health import HealthService
from app.services.project import ProjectService


def get_health_service(request: Request) -> HealthService:
    return HealthService(database=request.app.state.database, redis=request.app.state.redis)


def get_db_session(request: Request) -> Generator[Session, None, None]:
    database: DatabaseConnection = request.app.state.database
    session = database.get_session()
    try:
        yield session
    finally:
        session.close()


def get_project_service(session: Session = Depends(get_db_session)) -> ProjectService:
    return ProjectService(session)
