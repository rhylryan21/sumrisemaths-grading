import os
from typing import Annotated

from fastapi import Header, HTTPException

# Load once at module import
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
GRADING_API_KEY = os.getenv("GRADING_API_KEY", "")


def require_admin(
    x_admin_token: Annotated[str | None, Header(alias="x-admin-token")] = None,
) -> None:
    """
    Strict admin-only guard. Requires the X-Admin-Token header to match ADMIN_TOKEN.
    """
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured on server.")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized.")


def require_client(
    x_api_key: Annotated[str | None, Header(alias="x-api-key")] = None,
    x_admin_token: Annotated[str | None, Header(alias="x-admin-token")] = None,
) -> None:
    """
    Client/API guard. Accepts either:
      - X-Admin-Token that matches ADMIN_TOKEN (admins always allowed), or
      - X-Api-Key that matches GRADING_API_KEY.
    """
    # Admin token grants access
    if ADMIN_TOKEN and x_admin_token == ADMIN_TOKEN:
        return

    # Otherwise require the public API key
    if not GRADING_API_KEY:
        raise HTTPException(status_code=500, detail="GRADING_API_KEY not configured on server.")
    if x_api_key != GRADING_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized.")
