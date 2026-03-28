"""
SARC360 ERP - Tenant, Role, UserRole Models
عزل المستأجرين + نظام الصلاحيات
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Tenant(UUIDMixin, TimestampMixin, Base):
    """مستأجر — كل شركة/وحدة أعمال لها مستأجر منفصل."""
    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="e.g. sarc-001")
    legal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(10), nullable=True, default="SA")
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Tenant {self.slug} – {self.legal_name}>"


class Role(UUIDMixin, Base):
    """الأدوار المتاحة في النظام."""
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="super_admin | finance_hr | projects | employee | client"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<Role {self.code}>"


class UserRole(Base):
    """ربط المستخدم بدوره ضمن مستأجر معين."""
    __tablename__ = "user_roles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_user_roles_user", "tenant_id", "user_id"),
    )
