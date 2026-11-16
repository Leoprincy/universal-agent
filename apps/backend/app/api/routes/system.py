from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.system import SystemInfoResponse

router = APIRouter()


@router.get("/system/info", response_model=SystemInfoResponse, summary="Get non-sensitive system information")
def get_system_info(request: Request) -> SystemInfoResponse:
    settings: Settings = request.app.state.settings
    return SystemInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
