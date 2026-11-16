import asyncio
import logging

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.health import ComponentHealth

logger = logging.getLogger(__name__)

DATABASE_CONNECT_TIMEOUT_SECONDS = 1
DATABASE_POOL_TIMEOUT_SECONDS = 1
DATABASE_HEALTH_CHECK_TIMEOUT_SECONDS = 2.5


class DatabaseConnection:
    """Owns the SQLAlchemy engine and exposes a small health-check contract."""

    def __init__(self, database_url: str | None) -> None:
        self._engine: Engine | None = (
            create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=DATABASE_POOL_TIMEOUT_SECONDS,
                connect_args={"connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS},
            )
            if database_url
            else None
        )
        self._session_factory = (
            sessionmaker(bind=self._engine, autoflush=False, autocommit=False)
            if self._engine
            else None
        )

    @property
    def configured(self) -> bool:
        return self._engine is not None

    def get_session(self) -> Session:
        if self._session_factory is None:
            raise RuntimeError("Database connection is not configured")
        return self._session_factory()

    async def check(self) -> ComponentHealth:
        if self._engine is None:
            return ComponentHealth(status="not_configured", message="Database URL is not configured")
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._check_sync), timeout=DATABASE_HEALTH_CHECK_TIMEOUT_SECONDS
            )
            return ComponentHealth(status="connected", message="Database is reachable")
        except (asyncio.TimeoutError, SQLAlchemyError) as exc:
            logger.warning("Database health check failed (%s)", type(exc).__name__)
            return ComponentHealth(status="unavailable", message="Database is not reachable")

    def _check_sync(self) -> None:
        assert self._engine is not None
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
