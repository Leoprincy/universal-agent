import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import ApplicationError
from app.core.logging import configure_logging
from app.database.connection import DatabaseConnection
from app.database.redis_connection import RedisConnection
from app.schemas.errors import ErrorResponse

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(app_settings.log_level)
        database_url = (
            app_settings.database_url.get_secret_value() if app_settings.database_url else None
        )
        redis_url = app_settings.redis_url.get_secret_value() if app_settings.redis_url else None
        app.state.settings = app_settings
        app.state.database = DatabaseConnection(database_url)
        app.state.redis = RedisConnection(redis_url)
        logger.info("Application startup complete", extra={"environment": app_settings.environment})
        try:
            yield
        finally:
            try:
                await app.state.redis.close()
            finally:
                app.state.database.close()
            logger.info("Application shutdown complete")

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_: Request, exc: ApplicationError) -> JSONResponse:
        body = ErrorResponse(error={"code": exc.code, "message": exc.message})
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        safe_details = [
            {key: error[key] for key in ("type", "loc", "msg") if key in error}
            for error in exc.errors()
        ]
        body = ErrorResponse(
            error={
                "code": "validation_error",
                "message": "Request validation failed",
                "details": safe_details,
            }
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        body = ErrorResponse(error={"code": "http_error", "message": str(exc.detail)})
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(), headers=exc.headers)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error at %s", request.url.path, exc_info=exc)
        body = ErrorResponse(error={"code": "internal_error", "message": "An unexpected error occurred"})
        return JSONResponse(status_code=500, content=body.model_dump())

    return app


app = create_app()
