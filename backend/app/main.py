from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import config as config_routes
from app.api.routes import health as health_routes
from app.database import init_db

app = FastAPI(title="Engineering Command Center API", version="0.1.0")

# Local-first: frontend runs on localhost:3000, backend on localhost:8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    return {"service": "engineering-command-center-api", "status": "running"}


app.include_router(health_routes.router)
app.include_router(config_routes.router)
