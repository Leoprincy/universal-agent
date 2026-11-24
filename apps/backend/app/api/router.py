from fastapi import APIRouter

from app.api.routes import (
    experiments,
    health,
    integrations,
    jobs,
    ops,
    learnings,
    opportunities,
    projects,
    research,
    strategies,
    system,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(ops.router, tags=["ops"])
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
api_router.include_router(
    strategies.router,
    prefix="/projects/{project_id_or_slug}/strategies",
    tags=["strategies"],
)
api_router.include_router(
    experiments.router,
    prefix="/projects/{project_id_or_slug}/strategies",
    tags=["experiments"],
)
api_router.include_router(
    integrations.router,
    prefix="/projects/{project_id_or_slug}/integrations",
    tags=["integrations"],
)
api_router.include_router(
    learnings.router,
    prefix="/projects/{project_id_or_slug}/learnings",
    tags=["learnings"],
)
api_router.include_router(
    jobs.router,
    prefix="/projects/{project_id_or_slug}/jobs",
    tags=["jobs"],
)
