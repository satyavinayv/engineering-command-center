from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import actions as actions_routes
from app.api.routes import ai as ai_routes
from app.api.routes import calendar_api as calendar_routes
from app.api.routes import config as config_routes
from app.api.routes import dashboard as dashboard_routes
from app.api.routes import gitlab as gitlab_routes
from app.api.routes import gmail_api as gmail_router
from app.api.routes import health as health_routes
from app.api.routes import jira as jira_routes
from app.api.routes import sync as sync_routes
from app.api.routes import tests as tests_routes

from app.database import init_db
from app.services.scheduler import (
    start_scheduler,
    stop_scheduler,
)

app = FastAPI(
    title="Engineering Command Center API",
    version="0.1.0",
)

# Local-first:
# frontend = http://localhost:3000
# backend  = http://localhost:8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """
    Initialize the database and start background scheduling.
    """

    init_db()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    """
    Stop background scheduling during application shutdown.
    """

    stop_scheduler()


@app.get("/")
def root() -> dict:
    return {
        "service": "engineering-command-center-api",
        "status": "running",
    }


app.include_router(health_routes.router)
app.include_router(config_routes.router)
app.include_router(jira_routes.router)
app.include_router(gitlab_routes.router)
app.include_router(sync_routes.router)
app.include_router(tests_routes.router)
app.include_router(calendar_routes.router)
app.include_router(gmail_router.router)
app.include_router(actions_routes.router)
app.include_router(ai_routes.router)
app.include_router(dashboard_routes.router)