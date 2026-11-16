from typing import Literal

from pydantic import BaseModel, ConfigDict

ComponentState = Literal["connected", "not_configured", "unavailable"]
ApplicationState = Literal["healthy", "degraded"]


class ComponentHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ComponentState
    message: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ApplicationState
    application: Literal["running"] = "running"
    database: ComponentHealth
    redis: ComponentHealth
