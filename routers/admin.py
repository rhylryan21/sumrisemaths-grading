from fastapi import APIRouter, Depends

from bank import reload_bank
from deps.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/reload")
def admin_reload():
    n = reload_bank()
    return {"ok": True, "count": n}
