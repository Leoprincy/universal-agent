from fastapi import Request

from app.services.health import HealthService


def get_health_service(request: Request) -> HealthService:
    return HealthService(database=request.app.state.database, redis=request.app.state.redis)
