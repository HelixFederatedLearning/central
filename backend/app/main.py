# # from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.staticfiles import StaticFiles

# # from .core.settings import settings
# # from .db.session import init_db
# # from .routers import auth, deltas, models, rounds, settings as rsettings, infer
# # from .core.scheduler import scheduler_lifespan


# # app = FastAPI(title=settings.PROJECT_NAME, lifespan=scheduler_lifespan)

# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=settings.CORS_ORIGINS,
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )

# # # Serve model artifacts (new aggregated models will appear here)
# # app.mount(
# #     "/artifacts",
# #     StaticFiles(directory=str(settings.STORE_ROOT / "models")),
# #     name="artifacts",
# # )

# # # Routers
# # app.include_router(infer.router,   prefix=f"{settings.API_V1}", tags=["inference"])
# # app.include_router(auth.router,    prefix=f"{settings.API_V1}/auth", tags=["auth"])
# # app.include_router(deltas.router,  prefix=f"{settings.API_V1}", tags=["deltas"])
# # app.include_router(models.router,  prefix=f"{settings.API_V1}", tags=["models"])
# # app.include_router(rounds.router,  prefix=f"{settings.API_V1}", tags=["rounds"])
# # app.include_router(rsettings.router, prefix=f"{settings.API_V1}", tags=["settings"])


# # @app.on_event("startup")
# # def _startup():
# #     init_db()
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from pathlib import Path

# from .core.settings import settings
# from .db.session import init_db
# from .routers import auth, deltas, models, rounds, settings as rsettings, infer
# from .core.scheduler import scheduler_lifespan


# # Create app with lifespan so the scheduler runs automatically
# app = FastAPI(title=settings.PROJECT_NAME, lifespan=scheduler_lifespan)

# # Static: model artifacts are served from /artifacts
# app.mount(
#     "/artifacts",
#     StaticFiles(directory=str(settings.STORE_ROOT / "models")),
#     name="artifacts",
# )

# # CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Routers
# app.include_router(infer.router,   prefix=f"{settings.API_V1}", tags=["inference"])
# app.include_router(auth.router,    prefix=f"{settings.API_V1}/auth", tags=["auth"])
# app.include_router(deltas.router,  prefix=f"{settings.API_V1}", tags=["deltas"])
# app.include_router(models.router,  prefix=f"{settings.API_V1}", tags=["models"])
# app.include_router(rounds.router,  prefix=f"{settings.API_V1}", tags=["rounds"])
# app.include_router(rsettings.router, prefix=f"{settings.API_V1}", tags=["settings"])


# @app.on_event("startup")
# def _startup():
#     init_db()
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.settings import settings
from .db.session import init_db
from .routers import auth, deltas, models, rounds, settings as rsettings
from .routers import events as revents   # <-- add this
from fastapi.staticfiles import StaticFiles

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts", StaticFiles(directory=str(settings.STORE_ROOT / "models")), name="artifacts")

app.include_router(auth.router,    prefix=f"{settings.API_V1}/auth",    tags=["auth"])
app.include_router(deltas.router,  prefix=f"{settings.API_V1}",         tags=["deltas"])
app.include_router(models.router,  prefix=f"{settings.API_V1}",         tags=["models"])
app.include_router(rounds.router,  prefix=f"{settings.API_V1}",         tags=["rounds"])
app.include_router(rsettings.router,prefix=f"{settings.API_V1}",        tags=["settings"])
app.include_router(revents.router, prefix=f"{settings.API_V1}",         tags=["events"])  # <-- add this

@app.on_event("startup")
def _startup():
    init_db()
