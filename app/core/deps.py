"""
SARC360 ERP - FastAPI Dependencies
استخراج المستخدم الحالي + عزل المستأجر من JWT
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=True)


class CurrentUser:
    """Parsed JWT claims — injected as a FastAPI dependency."""
    def __init__(self, payload: dict):
        self.user_id: UUID = UUID(payload["sub"])
        self.tenant_id: UUID = UUID(payload["tid"])
        self.roles: list[str] = payload.get("roles", [])
        self.user_type: str = payload.get("user_type", "staff")
        raw_client = payload.get("client_id")
        self.client_id: UUID | None = UUID(raw_client) if raw_client else None

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    def require_role(self, *roles: str) -> None:
        if not self.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {roles}",
            )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
        return CurrentUser(payload)
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Convenient type aliases
DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
