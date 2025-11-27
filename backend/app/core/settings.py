from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    PROJECT_NAME: str = "DR Federated Central"
    API_V1: str = "/v1"
    SECRET_KEY: str = "change-me"      # JWT signing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    DB_URL: str = "sqlite:///./central.db"
    STORE_ROOT: Path = Path("./store").resolve()
    WINDOW_MINUTES: int = 360          # 6h
    EMA_DECAY: float = 0.997
    MIN_TOTAL: int = 1                 # MVP
    MIN_HOSP: int = 0                  # MVP
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    class Config:
        env_file = ".env"

settings = Settings()
settings.STORE_ROOT.mkdir(parents=True, exist_ok=True)
(settings.STORE_ROOT / "deltas").mkdir(exist_ok=True, parents=True)
(settings.STORE_ROOT / "models").mkdir(exist_ok=True, parents=True)
(settings.STORE_ROOT / "current").mkdir(exist_ok=True, parents=True)
