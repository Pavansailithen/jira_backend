from fastapi import APIRouter
from app.endpoints.v1 import (
    auth_api,
    admin_api,
    projects_api,
    stories_api,
    teams_api,
    notifications_api,
    password_reset_api,
    mode_switch_api,
    stats_api,
    epics_api
)

api_router = APIRouter()

api_router.include_router(auth_api.router)
api_router.include_router(admin_api.router)
api_router.include_router(projects_api.router)
api_router.include_router(stories_api.router)
api_router.include_router(teams_api.router)
api_router.include_router(notifications_api.router)
api_router.include_router(epics_api.router, prefix="/epics", tags=["Epics"])
api_router.include_router(password_reset_api.router)
api_router.include_router(mode_switch_api.router)
api_router.include_router(stats_api.router)
