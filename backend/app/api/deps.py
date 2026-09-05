"""
Single-user auth: a static API key sent as `X-API-Key`. This is
intentionally simple for a personal, local-first dashboard (spec section
38: don't overengineer a single-user tool). If/when the mobile companion
app exposes this backend beyond localhost, this is the first thing to
harden (e.g. move to short-lived tokens).
"""
from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
