"""
SARC360 ERP - User + Auth Models
المستخدمون + رموز التحقق + حدود المعدل
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    """مستخدم مرتبط بمستأجر."""
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="+9665...")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)

    # staff | employee | client
    user_type: Mapped[str] = mapped_column(String(20), nullable=False, default="staff")

    # Optional links
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_users_tenant", "tenant_id", "id"),
        Index("ux_users_email", "tenant_id", "email", unique=True),
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class AuthVerificationCode(UUIDMixin, Base):
    """رموز التحقق للبريد والجوال."""
    __tablename__ = "auth_verification_codes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False, comment="email | sms")
    purpose: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="signup_verify | login_verify | password_reset | change_contact"
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_auth_codes_lookup",
            "tenant_id", "user_id", "channel", "purpose", "expires_at"
        ),
    )


class AuthRateLimit(Base):
    """حدود معدل الطلبات لحماية المصادقة."""
    __tablename__ = "auth_rate_limits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    key_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="ip | email | phone | user_id")
    key_value: Mapped[str] = mapped_column(String(255), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_rate_limits_key", "key_type", "key_value", "window_start"),
    )
