"""
SARC360 ERP - RBAC Permission Models
نماذج نظام صلاحيات الوصول المبني على الأدوار
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


# ── Module constants ──────────────────────────────────────────────────────────
# Every protected module has a canonical string key used in permission_templates.
MODULES = [
    "employees",
    "projects",
    "timesheets",
    "invoices",
    "contracts",
    "clients",
    "expenses",
    "payroll",
    "suppliers",
    "cost_engine",
    "dashboard",
    "imports",
    "users",           # user management
    "audit_log",       # view audit events
    "settings",        # tenant settings
]


class PermissionTemplate(UUIDMixin, TimestampMixin, Base):
    """
    قالب صلاحيات لكل دور ووحدة وظيفية.
    Defines what a role can do in each module.
    One row per (role_code, module) pair.
    """
    __tablename__ = "permission_templates"

    role_code: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Matches roles.code"
    )
    module: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="e.g. invoices, payroll, employees"
    )

    # Action flags
    can_view: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_create: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_approve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_post: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("role_code", "module", name="uq_perm_role_module"),
        Index("ix_perm_role", "role_code"),
    )

    def __repr__(self) -> str:
        return f"<PermissionTemplate {self.role_code}:{self.module}>"


class UserPermissionOverride(UUIDMixin, TimestampMixin, Base):
    """
    تجاوز الصلاحيات لمستخدم محدد (مؤقت).
    Time-bound emergency grants or revocations per user per module/action.
    """
    __tablename__ = "user_permission_overrides"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="view | create | edit | approve | post | export"
    )
    # True = grant extra access, False = explicitly revoke
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    granted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="NULL = permanent override"
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_perm_override_user", "tenant_id", "user_id"),
        Index("ix_perm_override_expiry", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<UserPermissionOverride user={self.user_id} {self.module}.{self.action} granted={self.granted}>"


class UserProjectAssignment(UUIDMixin, TimestampMixin, Base):
    """
    ربط المستخدم بالمشاريع المسموح له بالوصول إليها.
    Used for Project Manager / Operations Coordinator scope isolation.
    If a user has a role that requires project-scoped access AND has rows here,
    only those projects are visible to them.
    """
    __tablename__ = "user_project_assignments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "project_id", name="uq_user_project"),
        Index("ix_user_project_user", "tenant_id", "user_id"),
        Index("ix_user_project_project", "tenant_id", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<UserProjectAssignment user={self.user_id} project={self.project_id}>"
