import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.core.config import get_settings


class Role(str, Enum):
    ANALYST = "analyst"   # read dashboards, export aggregates
    ADMIN = "admin"       # everything, including raw events
    SERVICE = "service"   # machine writes: events ingest, aggregation


# FUTURE: map the real role names from your auth system / RBAC module to ours.
ROLE_CLAIM_MAP = {"analyst": Role.ANALYST, "admin": Role.ADMIN, "service": Role.SERVICE}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role


def get_principal(x_api_key: Optional[str] = Header(default=None)) -> Principal:
    """
    >>> THE ONLY FUNCTION TO REPLACE WHEN REAL AUTH ARRIVES <<<

    Today: dummy API keys from .env.
    Future (JWT), replace the body with something like:
        claims = jwt.decode(token, settings.JWT_PUBLIC_KEY,
                            algorithms=["RS256"], audience=settings.JWT_AUDIENCE)
        return Principal(subject=claims["sub"], role=ROLE_CLAIM_MAP[claims["role"]])
    and change the parameter to HTTPBearer credentials. No route changes needed.
    """
    s = get_settings()
    configured = [(k, r) for k, r in (
        (s.ADMIN_API_KEY, Role.ADMIN),
        (s.ANALYST_API_KEY, Role.ANALYST),
        (s.API_KEY, Role.SERVICE),
    ) if k]
    if not configured:   # fail closed
        raise HTTPException(503, "Authentication is not configured on the server")
    if x_api_key:
        for key, role in configured:
            if secrets.compare_digest(x_api_key.encode(), key.encode()):
                return Principal(subject=f"{role.value}-key", role=role)
    raise HTTPException(401, "Invalid or missing credentials",
                        headers={"WWW-Authenticate": "ApiKey"})


def require_role(*allowed: Role):
    allow = set(allowed) | {Role.ADMIN}   # admin always passes

    def dependency(p: Principal = Depends(get_principal)) -> Principal:
        if p.role not in allow:
            raise HTTPException(403, "Insufficient role for this action")
        return p

    return dependency