from pydantic import BaseModel, ConfigDict


class SystemInfoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    environment: str
