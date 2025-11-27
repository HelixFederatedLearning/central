# app/db/models.py
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import SQLModel, Field

UTCNOW = lambda: datetime.now(timezone.utc)


class BaseModel(SQLModel):
    """Common config to silence pydantic protected namespace warnings."""
    model_config = {
        "protected_namespaces": (),  # allow fields like model_id, model_arch, etc.
        "from_attributes": True,
    }


# ---------------------------
# Core settings singleton
# ---------------------------

class Setting(BaseModel, table=True):
    __tablename__ = "setting"
    id: int = Field(default=1, primary_key=True)
    window_minutes: int = Field(default=10)
    ema_decay: float = Field(default=0.0)
    min_total: int = Field(default=1)
    min_hosp: int = Field(default=0)
    current_model_id: Optional[str] = Field(default=None, foreign_key="model.id")


# ---------------------------
# Saved global model artifacts
# ---------------------------

class Model(BaseModel, table=True):
    __tablename__ = "model"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    version: str
    artifact_path: str
    checksum: str
    is_current: bool = Field(default=False)
    created_at: datetime = Field(default_factory=UTCNOW)


# ---------------------------
# FL round tracking
# ---------------------------

class Round(BaseModel, table=True):
    __tablename__ = "round"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    status: str = Field(default="open")        # "open" | "closed"
    created_at: datetime = Field(default_factory=UTCNOW)
    closed_at: Optional[datetime] = None


# ---------------------------
# Client deltas (per round)
# ---------------------------

class Delta(BaseModel, table=True):
    __tablename__ = "delta"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)

    round_id: str = Field(foreign_key="round.id")
    client_id: str

    # kind: "hospital" | "patient"
    kind: str

    # weighting for aggregation
    num_examples: int = Field(default=0)

    # path to .pt containing {'bb': {...}, 'hd': {...?}}
    blob_path: str

    # metadata
    sd_keys_hash: str = Field(default="")
    model_arch: str = Field(default="tv_effnet_b3")

    created_at: datetime = Field(default_factory=UTCNOW)
