from fastapi import APIRouter

from app.api.routes import health, opportunities, projects, research, system

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    research.router,
    prefix="/projects/{project_id_or_slug}/research",
    tags=["research"],
)
api_router.include_router(
    opportunities.router,
    prefix="/projects/{project_id_or_slug}/opportunities",
    tags=["opportunities"],
)
