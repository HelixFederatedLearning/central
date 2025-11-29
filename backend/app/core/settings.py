# # from pydantic_settings import BaseSettings
# # from pathlib import Path


# # class Settings(BaseSettings):
# #     PROJECT_NAME: str = "DR Federated Central"
# #     API_V1: str = "/v1"
# #     SECRET_KEY: str = "change-me"      # JWT signing
# #     ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
# #     DB_URL: str = "sqlite:///./central.db"
# #     STORE_ROOT: Path = Path("./store").resolve()
# #     WINDOW_MINUTES: int = 1          # 6h
# #     EMA_DECAY: float = 0.997
# #     MIN_TOTAL: int = 1                 # MVP
# #     MIN_HOSP: int = 0                  # MVP
# #     CORS_ORIGINS: list[str] = [
# #     "http://localhost:5173",  # central UI
# #     "http://localhost:5174",  # hospital UI (if it calls central directly for /v1/events)
# # ]
# #     class Config:
# #         env_file = ".env"

# # settings = Settings()
# # settings.STORE_ROOT.mkdir(parents=True, exist_ok=True)
# # (settings.STORE_ROOT / "deltas").mkdir(exist_ok=True, parents=True)
# # (settings.STORE_ROOT / "models").mkdir(exist_ok=True, parents=True)
# # (settings.STORE_ROOT / "current").mkdir(exist_ok=True, parents=True)
# # app/core/settings.py
# from pydantic_settings import BaseSettings
# from pathlib import Path
# from typing import List


# class Settings(BaseSettings):
#     PROJECT_NAME: str = "DR Federated Central"
#     API_V1: str = "/v1"

#     SECRET_KEY: str = "change-me"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

#     DB_URL: str = "sqlite:///./central.db"

#     # Root directory for models/deltas
#     STORE_ROOT: Path = Path("./store").resolve()

#     # ---- FL behaviour ----
#     WINDOW_MINUTES: int = 2      # ⬅️ 2-minute window
#     EMA_DECAY: float = 0.997
#     MIN_TOTAL: int = 2          # ⬅️ at least 2 deltas to aggregate
#     MIN_HOSP: int = 0

#     # CORS for central + hospital UI
#     CORS_ORIGINS: List[str] = [
#         "http://localhost:5173",  # central UI
#         "http://localhost:5174",  # hospital UI (if it ever calls /v1/events)
#     ]

#     class Config:
#         env_file = ".env"


# settings = Settings()

# settings.STORE_ROOT.mkdir(parents=True, exist_ok=True)
# (settings.STORE_ROOT / "deltas").mkdir(parents=True, exist_ok=True)
# (settings.STORE_ROOT / "models").mkdir(parents=True, exist_ok=True)
# (settings.STORE_ROOT / "current").mkdir(parents=True, exist_ok=True)
# app/core/settings.py
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "DR Federated Central"
    API_V1: str = "/v1"

    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    DB_URL: str = "sqlite:///./central.db"

    # Root directory for models/deltas
    STORE_ROOT: Path = Path("./store").resolve()

    # ---- FL behaviour ----
    WINDOW_MINUTES: int = 2      # default window length (minutes)
    EMA_DECAY: float = 0.997
    MIN_TOTAL: int = 2           # at least 2 deltas required (window starts on 2nd)
    MIN_HOSP: int = 0

    # CORS for central + hospital UI
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",  # central UI
        "http://localhost:5174",  # hospital UI
    ]

    class Config:
        env_file = ".env"


settings = Settings()

settings.STORE_ROOT.mkdir(parents=True, exist_ok=True)
(settings.STORE_ROOT / "deltas").mkdir(parents=True, exist_ok=True)
(settings.STORE_ROOT / "models").mkdir(parents=True, exist_ok=True)
(settings.STORE_ROOT / "current").mkdir(parents=True, exist_ok=True)
