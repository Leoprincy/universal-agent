from fastapi import APIRouter, Depends

from app.api.dependencies import get_health_service
from app.schemas.health import HealthResponse
from app.services.health import HealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Check application and infrastructure health")
async def get_health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return await service.get_health()
