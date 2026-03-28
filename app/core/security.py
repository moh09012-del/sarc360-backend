"""
SARC360 ERP - Security Utilities
JWT إصدار + التحقق · تشفير كلمات المرور
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_refresh_token(
    user_id: UUID,
    tenant_id: UUID,
    expires_days: int | None = None,
) -> str:
    """Issue a long-lived refresh token (typ=refresh, no roles embedded)."""
    exp_days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "typ": "refresh",
        "iat": now,
        "exp": now + timedelta(days=exp_days),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    roles: list[str],
    user_type: str = "staff",
    client_id: UUID | None = None,
    expires_minutes: int | None = None,
) -> str:
    exp_min = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "typ": "access",
        "roles": roles,
        "user_type": user_type,
        "iat": now,
        "exp": now + timedelta(minutes=exp_min),
        "jti": secrets.token_hex(16),
    }
    if client_id:
        payload["client_id"] = str(client_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Verification codes ────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP."""
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def hash_code(code: str, salt: str | None = None) -> tuple[str, str]:
    """Hash an OTP for storage. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()
    return digest, salt


def verify_code(code: str, stored_hash: str, salt: str) -> bool:
    digest, _ = hash_code(code, salt)
    return secrets.compare_digest(digest, stored_hash)
