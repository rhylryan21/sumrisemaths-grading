from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime | None
    total: int
    correct: int
    duration_ms: int | None = None
    # keep items optional; usually excluded in list views
    items: list[Any] | dict | None = None
