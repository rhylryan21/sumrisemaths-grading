# services/grading/routers/health.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory
from db import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/db")
def health_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db_error: {type(e).__name__}: {e}")


def _alembic_heads() -> list[str]:
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    return list(script.get_heads())


@router.get("/migrations")
def health_migrations():
    heads: list[str] = []
    db_ver = None
    try:
        heads = _alembic_heads()
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            try:
                db_ver = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
            except Exception:
                db_ver = None
    except Exception as e:
        return {
            "ok": False,
            "error": f"db_connect_failed: {e}",
            "code_heads": heads,
            "db_version": db_ver,
        }

    synced = (db_ver in heads) if heads else False
    return {"ok": synced, "synced": synced, "db_version": db_ver, "code_heads": heads}
