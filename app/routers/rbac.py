"""
SARC360 ERP - RBAC Management Router
إدارة الصلاحيات وتعيين المشاريع

Endpoints:
  GET  /rbac/permission-matrix          — view full role→module matrix
  GET  /rbac/my-permissions             — current user's effective permissions
  POST /rbac/project-assignments        — assign user to project (super_admin/hr_manager)
  DELETE /rbac/project-assignments/{id} — remove assignment
  POST /rbac/overrides                  — grant/revoke temporary override
  DELETE /rbac/overrides/{id}           — remove override
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AuthUser, DbSession
from app.models.rbac import PermissionTemplate, UserPermissionOverride, UserProjectAssignment
from app.services.permissions import check_permission

router = APIRouter(prefix="/rbac", tags=["RBAC"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PermissionMatrixRow(BaseModel):
    role_code: str
    module: str
    can_view: bool
    can_create: bool
    can_edit: bool
    can_approve: bool
    can_post: bool
    can_export: bool


class MyPermissions(BaseModel):
    roles: list[str]
    permissions: list[PermissionMatrixRow]
    project_scoped: bool


class ProjectAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    project_id: uuid.UUID


class ProjectAssignmentOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    assigned_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PermissionOverrideCreate(BaseModel):
    user_id: uuid.UUID
    module: str
    action: str
    granted: bool = True
    expires_at: datetime | None = None
    reason: str | None = None


class PermissionOverrideOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    module: str
    action: str
    granted: bool
    expires_at: datetime | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/permission-matrix", response_model=list[PermissionMatrixRow])
async def get_permission_matrix(user: AuthUser, db: DbSession):
    """Full permission matrix — super_admin or auditor only."""
    user.require_role("super_admin", "auditor")

    rows = (await db.execute(
        select(PermissionTemplate).order_by(
            PermissionTemplate.role_code, PermissionTemplate.module
        )
    )).scalars().all()

    return [
        PermissionMatrixRow(
            role_code=r.role_code,
            module=r.module,
            can_view=r.can_view,
            can_create=r.can_create,
            can_edit=r.can_edit,
            can_approve=r.can_approve,
            can_post=r.can_post,
            can_export=r.can_export,
        )
        for r in rows
    ]


@router.get("/my-permissions", response_model=MyPermissions)
async def get_my_permissions(user: AuthUser, db: DbSession):
    """Current user's effective permissions (from role templates + overrides)."""
    from app.services.permissions import _PROJECT_SCOPED_ROLES, get_user_project_ids

    rows = (await db.execute(
        select(PermissionTemplate).where(
            PermissionTemplate.role_code.in_(user.roles)
        ).order_by(PermissionTemplate.module)
    )).scalars().all()

    project_ids = await get_user_project_ids(user, db)
    is_scoped = project_ids is not None  # None = unrestricted

    return MyPermissions(
        roles=user.roles,
        permissions=[
            PermissionMatrixRow(
                role_code=r.role_code,
                module=r.module,
                can_view=r.can_view,
                can_create=r.can_create,
                can_edit=r.can_edit,
                can_approve=r.can_approve,
                can_post=r.can_post,
                can_export=r.can_export,
            )
            for r in rows
        ],
        project_scoped=is_scoped,
    )


@router.post("/project-assignments", response_model=ProjectAssignmentOut, status_code=201)
async def assign_user_to_project(body: ProjectAssignmentCreate, user: AuthUser, db: DbSession):
    """Assign a user to a project for scoped access. super_admin or hr_manager only."""
    user.require_role("super_admin", "hr_manager", "finance_hr")

    existing = (await db.execute(
        select(UserProjectAssignment).where(
            and_(
                UserProjectAssignment.tenant_id == user.tenant_id,
                UserProjectAssignment.user_id == body.user_id,
                UserProjectAssignment.project_id == body.project_id,
            )
        )
    )).scalar_one_or_none()

    if existing:
        return existing

    assignment = UserProjectAssignment(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        project_id=body.project_id,
        assigned_by=user.user_id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.delete("/project-assignments/{assignment_id}", status_code=204)
async def remove_project_assignment(assignment_id: uuid.UUID, user: AuthUser, db: DbSession):
    """Remove a project assignment. super_admin or hr_manager only."""
    user.require_role("super_admin", "hr_manager", "finance_hr")

    row = (await db.execute(
        select(UserProjectAssignment).where(
            and_(
                UserProjectAssignment.id == assignment_id,
                UserProjectAssignment.tenant_id == user.tenant_id,
            )
        )
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")

    await db.delete(row)
    await db.commit()


@router.post("/overrides", response_model=PermissionOverrideOut, status_code=201)
async def create_permission_override(
    body: PermissionOverrideCreate,
    user: AuthUser,
    db: DbSession,
):
    """Grant or revoke a time-bound permission override. super_admin only."""
    user.require_role("super_admin")

    override = UserPermissionOverride(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        module=body.module,
        action=body.action,
        granted=body.granted,
        granted_by=user.user_id,
        expires_at=body.expires_at,
        reason=body.reason,
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)
    return override


@router.delete("/overrides/{override_id}", status_code=204)
async def remove_permission_override(override_id: uuid.UUID, user: AuthUser, db: DbSession):
    """Remove a permission override. super_admin only."""
    user.require_role("super_admin")

    row = (await db.execute(
        select(UserPermissionOverride).where(
            and_(
                UserPermissionOverride.id == override_id,
                UserPermissionOverride.tenant_id == user.tenant_id,
            )
        )
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Override not found")

    await db.delete(row)
    await db.commit()
