# grading/routers/attempts.py

import os

from fastapi import APIRouter, HTTPException, Request

from db import SessionLocal
from models import Attempt
from schemas.attempts import AttemptOut

router = APIRouter(prefix="/attempts", tags=["attempts"])


def _check_client(request: Request) -> None:
    """
    Accept either:
      - x-api-key     matching GRADING_API_KEY, or
      - x-admin-token matching ADMIN_TOKEN
    """
    want_admin = os.environ.get("ADMIN_TOKEN", "")
    want_api = os.environ.get("GRADING_API_KEY", "")

    got_admin = request.headers.get("x-admin-token", "")
    got_api = request.headers.get("x-api-key", "")

    ok_admin = bool(want_admin) and (got_admin == want_admin)
    ok_api = bool(want_api) and (got_api == want_api)

    if not (ok_admin or ok_api):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/recent-list")
def attempts_recent(request: Request, limit: int = 20):
    _check_client(request)
    limit = max(1, min(limit, 100))

    with SessionLocal() as db:
        items = db.query(Attempt).order_by(Attempt.created_at.desc()).limit(limit).all()

    # Reuse schema; exclude potentially large JSON "items"
    rows = [AttemptOut.model_validate(a).model_dump(exclude={"items"}) for a in items]
    return {"ok": True, "items": rows, "count": len(rows)}


@router.get("/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: int):
    # Public endpoint: no admin token required
    with SessionLocal() as db:
        a = db.get(Attempt, attempt_id)
        if not a:
            raise HTTPException(status_code=404, detail="Attempt not found")
        return AttemptOut.model_validate(a)
