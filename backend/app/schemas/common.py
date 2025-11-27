from pydantic import BaseModel
from datetime import datetime

class ModelInfo(BaseModel):
    id: str
    version: str
    checksum: str
    created_at: datetime
    url: str
