from __future__ import annotations

import os

from fastapi import APIRouter, Request

from bank import reload_bank

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reload")
def reload_questions(request: Request):
    expected = os.getenv("ADMIN_TOKEN") or ""
    provided = request.headers.get("x-admin-token")

    if not expected:
        return {"ok": False, "error": "ADMIN_TOKEN not configured on server."}
    if provided != expected:
        return {"ok": False, "error": "unauthorized"}

    n = reload_bank()
    return {"ok": True, "count": n}
