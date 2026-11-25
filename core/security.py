import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = get_settings().API_KEY
    if not expected:
        # Fail closed: a missing server setting must never leave writes open
        raise HTTPException(status_code=503, detail="API key is not configured on the server")
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )