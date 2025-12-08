from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./grading.db")


class Base(DeclarativeBase): ...


# Use SQLite connect args only when it's SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # drops dead connections automatically
    pool_size=5,  # small, safe default on Render
    max_overflow=0,  # avoid bursting too many connections
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
