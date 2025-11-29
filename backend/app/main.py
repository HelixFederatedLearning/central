# app/main.py
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.settings import settings
from .db.session import init_db
from .core.scheduler import scheduler_loop   # <<< NOTE: from .core.scheduler
from .routers import (
    auth,
    deltas,
    models,
    rounds,
    settings as rsettings,
    events,   # SSE router
)

app = FastAPI(title=settings.PROJECT_NAME)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Artifacts
app.mount(
    "/artifacts",
    StaticFiles(directory=str(settings.STORE_ROOT / "models")),
    name="artifacts",
)

# Routers

app.include_router(auth.router,      prefix=f"{settings.API_V1}/auth",    tags=["auth"])
app.include_router(deltas.router,    prefix=f"{settings.API_V1}",         tags=["deltas"])
app.include_router(models.router,    prefix=f"{settings.API_V1}",         tags=["models"])
app.include_router(rounds.router,    prefix=f"{settings.API_V1}",         tags=["rounds"])
app.include_router(rsettings.router, prefix=f"{settings.API_V1}",         tags=["settings"])
app.include_router(events.router,    prefix=f"{settings.API_V1}",         tags=["events"])  # -> /v1/events




@app.on_event("startup")
def _startup() -> None:
    init_db()
    # start background scheduler
    asyncio.create_task(scheduler_loop())
