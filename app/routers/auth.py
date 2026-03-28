"""
SARC360 ERP - Auth Router
POST /auth/signup
POST /auth/login
POST /auth/refresh
GET  /auth/me
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import AuthUser, DbSession
from app.core.security import create_access_token, create_refresh_token, decode_access_token, hash_password, verify_password
from app.models.tenant import Role, Tenant, UserRole
from app.models.user import AuthRateLimit, User
from app.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenResponse, UserRead
from app.services.audit import log_event

router = APIRouter(prefix="/auth", tags=["Auth"])

_MAX_LOGIN_ATTEMPTS = 5
_BLOCK_WINDOW_SECONDS = 900  # 15 min


# ── Rate limiting helpers ──────────────────────────────────────────────────────

async def _check_rate_limit(db: DbSession, key_type: str, key_value: str) -> None:
    """Block if too many attempts in the current window."""
    now = datetime.now(tz=timezone.utc)
    res = await db.execute(
        select(AuthRateLimit).where(
            AuthRateLimit.key_type == key_type,
            AuthRateLimit.key_value == key_value,
        ).order_by(AuthRateLimit.window_start.desc()).limit(1)
    )
    rl = res.scalar_one_or_none()

    if rl and rl.blocked_until and rl.blocked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Try again after {rl.blocked_until.isoformat()}.",
        )

    if rl and (now - rl.window_start).total_seconds() < rl.window_seconds:
        rl.count += 1
        if rl.count >= _MAX_LOGIN_ATTEMPTS:
            from datetime import timedelta
            rl.blocked_until = now + timedelta(seconds=_BLOCK_WINDOW_SECONDS)
    else:
        rl = AuthRateLimit(
            key_type=key_type,
            key_value=key_value,
            window_seconds=_BLOCK_WINDOW_SECONDS,
            window_start=now,
            count=1,
        )
        db.add(rl)

    await db.flush()


async def _reset_rate_limit(db: DbSession, key_type: str, key_value: str) -> None:
    res = await db.execute(
        select(AuthRateLimit).where(
            AuthRateLimit.key_type == key_type,
            AuthRateLimit.key_value == key_value,
        ).order_by(AuthRateLimit.window_start.desc()).limit(1)
    )
    rl = res.scalar_one_or_none()
    if rl:
        rl.count = 0
        rl.blocked_until = None
        await db.flush()


# ── GET roles for a user ───────────────────────────────────────────────────────

async def _get_user_roles(db: DbSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
    res = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
    )
    return [row[0] for row in res.all()]


# ── POST /auth/signup ─────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             summary="Register a new user")
async def signup(payload: SignupRequest, db: DbSession, request: Request) -> TokenResponse:
    # Validate tenant exists and is active
    tenant_res = await db.execute(
        select(Tenant).where(Tenant.id == payload.tenant_id, Tenant.is_active.is_(True))
    )
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    # Enforce max_users
    user_count_res = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == payload.tenant_id, User.is_active.is_(True))
    )
    user_count = user_count_res.scalar_one()
    if user_count >= tenant.max_users:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tenant has reached the maximum of {tenant.max_users} users.",
        )

    # Duplicate email check
    dup_res = await db.execute(
        select(User).where(User.tenant_id == payload.tenant_id, User.email == payload.email)
    )
    if dup_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        tenant_id=payload.tenant_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone_e164=payload.phone_e164,
        user_type=payload.user_type,
        client_id=payload.client_id,
        employee_id=payload.employee_id,
    )
    db.add(user)
    await db.flush()

    # Assign default role based on user_type
    role_code_map = {"staff": "finance_hr", "employee": "employee", "client": "client"}
    role_code = role_code_map.get(payload.user_type, "employee")
    role_res = await db.execute(select(Role).where(Role.code == role_code))
    role = role_res.scalar_one_or_none()
    if role:
        db.add(UserRole(tenant_id=payload.tenant_id, user_id=user.id, role_id=role.id))

    await db.flush()
    await log_event(db, tenant_id=payload.tenant_id, actor_user_id=user.id,
                    action="create", entity_type="users", entity_id=user.id,
                    ip_address=request.client.host if request.client else None)
    await db.commit()

    roles = await _get_user_roles(db, payload.tenant_id, user.id)
    token = create_access_token(
        user_id=user.id,
        tenant_id=payload.tenant_id,
        roles=roles,
        user_type=user.user_type,
        client_id=user.client_id,
    )
    refresh = create_refresh_token(user_id=user.id, tenant_id=payload.tenant_id)
    return TokenResponse(
        access_token=token,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        tenant_id=payload.tenant_id,
        roles=roles,
        user_type=user.user_type,
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Login and get JWT")
async def login(payload: LoginRequest, db: DbSession, request: Request) -> TokenResponse:
    ip = request.client.host if request.client else "unknown"
    key_val = f"{payload.tenant_id}:{payload.email}"

    await _check_rate_limit(db, "email", key_val)

    user_res = await db.execute(
        select(User).where(
            User.tenant_id == payload.tenant_id,
            User.email == payload.email,
            User.is_active.is_(True),
        )
    )
    user = user_res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        await db.commit()  # persist rate limit increment
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await _reset_rate_limit(db, "email", key_val)

    user.last_login_at = datetime.now(tz=timezone.utc)
    await db.flush()
    await log_event(db, tenant_id=payload.tenant_id, actor_user_id=user.id,
                    action="login", entity_type="users", entity_id=user.id,
                    ip_address=ip)
    await db.commit()

    roles = await _get_user_roles(db, payload.tenant_id, user.id)
    token = create_access_token(
        user_id=user.id,
        tenant_id=payload.tenant_id,
        roles=roles,
        user_type=user.user_type,
        client_id=user.client_id,
    )
    refresh = create_refresh_token(user_id=user.id, tenant_id=payload.tenant_id)
    return TokenResponse(
        access_token=token,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        tenant_id=payload.tenant_id,
        roles=roles,
        user_type=user.user_type,
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token using refresh token")
async def refresh_token(payload: RefreshRequest, db: DbSession) -> TokenResponse:
    try:
        claims = decode_access_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if claims.get("typ") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token.",
        )
    user_id = uuid.UUID(claims["sub"])
    tenant_id = uuid.UUID(claims["tid"])
    user_res = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
    )
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
    roles = await _get_user_roles(db, tenant_id, user_id)
    new_access = create_access_token(
        user_id=user_id, tenant_id=tenant_id,
        roles=roles, user_type=user.user_type, client_id=user.client_id,
    )
    new_refresh = create_refresh_token(user_id=user_id, tenant_id=tenant_id)
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        user_type=user.user_type,
    )


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserRead, summary="Get current user profile")
async def me(cu: AuthUser, db: DbSession) -> UserRead:
    res = await db.execute(
        select(User).where(User.id == cu.user_id, User.tenant_id == cu.tenant_id)
    )
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserRead.model_validate(user)
