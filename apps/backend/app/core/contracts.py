from typing import Literal, Protocol

from app.schemas.health import ComponentHealth


class AsyncConnectivityCheck(Protocol):
    async def check(self) -> ComponentHealth: ...


ConnectivityState = Literal["connected", "not_configured", "unavailable"]
