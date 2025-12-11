from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import JSON, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    total: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    items: Mapped[dict] = mapped_column(JSON)  # store per-question results (simple)
    duration_ms: Mapped[int] = mapped_column(sa.Integer, nullable=True)
    # optional: user/session later
