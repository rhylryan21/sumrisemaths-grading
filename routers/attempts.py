import os

from fastapi import APIRouter, HTTPException, Request

from db import SessionLocal
from models import Attempt
from schemas.attempts import AttemptOut

router = APIRouter(prefix="/attempts", tags=["attempts"])


def _check_admin(request: Request):
    want = os.environ.get("ADMIN_TOKEN", "")
    got = request.headers.get("x-admin-token", "")
    if not want or got != want:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/recent-list")
def attempts_recent(request: Request, limit: int = 20):
    _check_admin(request)
    limit = max(1, min(limit, 100))
    rows = []
    # Use ORM so created_at is a proper datetime, etc.
    with SessionLocal() as db:
        items = db.query(Attempt).order_by(Attempt.created_at.desc()).limit(limit).all()

    # Reuse the Pydantic model to serialize, but exclude the potentially large JSON "items" field
    rows = [AttemptOut.model_validate(a).model_dump(exclude={"items"}) for a in items]
    return {"ok": True, "items": rows, "count": len(rows)}


@router.get("/{attempt_id}", response_model=AttemptOut)
def get_attempt(request: Request, attempt_id: int):
    _check_admin(request)  # remove if you want this public
    with SessionLocal() as db:
        a = db.get(Attempt, attempt_id)
        if not a:
            raise HTTPException(status_code=404, detail="Attempt not found")
        return a  # FastAPI serializes via response_model
