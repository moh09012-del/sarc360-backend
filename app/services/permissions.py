"""
SARC360 ERP - Permission Service
خدمة التحقق من الصلاحيات المبنية على الأدوار

Provides:
  - check_permission(user, module, action, db) → bool
  - require_permission(module, action) → FastAPI dependency
  - get_user_project_ids(user, db) → list[UUID] | None  (None = no restriction)
  - mask_fields(data, user, sensitive_fields) → data with masked values
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthUser, CurrentUser, get_current_user
from app.models.rbac import PermissionTemplate, UserPermissionOverride, UserProjectAssignment

# ── Roles that are exempt from permission_templates checks ────────────────────
# super_admin always has full access; we skip DB lookup for performance.
_BYPASS_ROLES = {"super_admin"}

# ── Roles that require project-scope isolation ────────────────────────────────
_PROJECT_SCOPED_ROLES = {"project_manager", "operations_coordinator"}

# ── Field masking: roles that may NOT see sensitive fields ────────────────────
# Fields masked when the viewer's role is NOT in the allowed set.
_SENSITIVE_FIELDS: dict[str, set[str]] = {
    # salary, basic_salary, overtime_rate, allowances — hidden from non-finance/non-HR
    "salary": {"super_admin", "general_manager", "finance_hr", "finance_manager",
               "accountant", "hr_manager", "payroll_officer", "auditor"},
    "basic_salary": {"super_admin", "general_manager", "finance_hr", "finance_manager",
                     "accountant", "hr_manager", "payroll_officer", "auditor"},
    "daily_rate": {"super_admin", "general_manager", "finance_hr", "finance_manager",
                   "accountant", "hr_manager", "payroll_officer", "auditor"},
    "hourly_rate": {"super_admin", "general_manager", "finance_hr", "finance_manager",
                    "accountant", "hr_manager", "payroll_officer", "auditor", "project_manager"},
    # Invoice margin / cost — hidden from BD and client portal
    "margin": {"super_admin", "general_manager", "finance_hr", "finance_manager",
               "accountant", "auditor"},
    "cost_amount": {"super_admin", "general_manager", "finance_hr", "finance_manager",
                    "accountant", "auditor"},
    # Banking / identity — maximum restriction
    "iban": {"super_admin", "finance_hr", "finance_manager", "payroll_officer", "hr_manager"},
    "iqama_number": {"super_admin", "finance_hr", "finance_manager", "hr_manager"},
    "passport_number": {"super_admin", "finance_hr", "finance_manager", "hr_manager"},
}

_MASK_VALUE = "****"


# ─────────────────────────────────────────────────────────────────────────────
# Core permission check
# ─────────────────────────────────────────────────────────────────────────────

async def check_permission(
    user: CurrentUser,
    module: str,
    action: str,
    db: AsyncSession,
) -> bool:
    """
    Return True if the user has the given action on the given module.

    Order of precedence:
      1. super_admin → always True
      2. user_permission_overrides (explicit user-level grants/revocations, time-bound)
      3. permission_templates for the user's role(s)
    """
    # 1. Bypass for super_admin
    if any(r in _BYPASS_ROLES for r in user.roles):
        return True

    now = datetime.now(tz=timezone.utc)

    # 2. Check user-level overrides (most specific wins)
    override_q = select(UserPermissionOverride).where(
        and_(
            UserPermissionOverride.tenant_id == user.tenant_id,
            UserPermissionOverride.user_id == user.user_id,
            UserPermissionOverride.module == module,
            UserPermissionOverride.action == action,
            (UserPermissionOverride.expires_at == None)  # noqa: E711
            | (UserPermissionOverride.expires_at > now),
        )
    ).order_by(UserPermissionOverride.created_at.desc()).limit(1)

    override_row = (await db.execute(override_q)).scalar_one_or_none()
    if override_row is not None:
        return override_row.granted

    # 3. Check permission_templates for each of the user's roles
    if not user.roles:
        return False

    action_col = _action_column(action)
    if action_col is None:
        return False

    tmpl_q = select(PermissionTemplate).where(
        and_(
            PermissionTemplate.role_code.in_(user.roles),
            PermissionTemplate.module == module,
        )
    )
    rows = (await db.execute(tmpl_q)).scalars().all()
    if not rows:
        return False

    # Any role that grants this action is sufficient
    return any(getattr(row, action_col) for row in rows)


def _action_column(action: str) -> str | None:
    """Map action string → PermissionTemplate column name."""
    mapping = {
        "view": "can_view",
        "create": "can_create",
        "edit": "can_edit",
        "approve": "can_approve",
        "post": "can_post",
        "export": "can_export",
    }
    return mapping.get(action)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependency factories
# ─────────────────────────────────────────────────────────────────────────────

def require_permission(module: str, action: str):
    """
    FastAPI dependency that raises 403 if the user lacks the required permission.

    Usage:
        @router.get("/invoices", dependencies=[Depends(require_permission("invoices", "view"))])
    """
    async def _dep(
        user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        allowed = await check_permission(user, module, action, db)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {module}.{action}",
            )
        return user

    return _dep


# ─────────────────────────────────────────────────────────────────────────────
# Project-scope isolation
# ─────────────────────────────────────────────────────────────────────────────

async def get_user_project_ids(
    user: CurrentUser,
    db: AsyncSession,
) -> list[UUID] | None:
    """
    Returns the list of project UUIDs the user is scoped to, or None if
    the user has full project visibility (no scope restriction).

    Rules:
      - super_admin, general_manager, finance_hr, finance_manager, accountant,
        hr_manager, auditor → None (unrestricted)
      - project_manager, operations_coordinator → restricted to user_project_assignments
      - All others → restricted to assigned projects (empty list = sees nothing)
    """
    unrestricted = {
        "super_admin", "general_manager", "finance_hr", "finance_manager",
        "accountant", "hr_manager", "auditor", "finance_hr",
    }
    if any(r in unrestricted for r in user.roles):
        return None

    # Fetch assigned project IDs
    q = select(UserProjectAssignment.project_id).where(
        and_(
            UserProjectAssignment.tenant_id == user.tenant_id,
            UserProjectAssignment.user_id == user.user_id,
        )
    )
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Field-level masking
# ─────────────────────────────────────────────────────────────────────────────

def mask_sensitive_fields(data: dict[str, Any], viewer_roles: list[str]) -> dict[str, Any]:
    """
    Replace sensitive field values with '****' if the viewer's roles do not
    include any role in the allowed set for that field.

    Works on flat dicts. Call before returning from a router.
    """
    if any(r in _BYPASS_ROLES for r in viewer_roles):
        return data  # super_admin sees everything

    result = dict(data)
    for field, allowed_roles in _SENSITIVE_FIELDS.items():
        if field in result and not any(r in allowed_roles for r in viewer_roles):
            result[field] = _MASK_VALUE
    return result


def mask_obj(obj: Any, viewer_roles: list[str]) -> Any:
    """
    Mask sensitive fields on a Pydantic model instance or plain dict.
    Returns the same type.
    """
    if hasattr(obj, "model_dump"):
        # Pydantic v2
        data = obj.model_dump()
        masked = mask_sensitive_fields(data, viewer_roles)
        return obj.model_copy(update=masked)
    elif isinstance(obj, dict):
        return mask_sensitive_fields(obj, viewer_roles)
    return obj
