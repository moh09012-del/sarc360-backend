"""
SARC360 ERP - Audit Trail
سجل تدقيق كامل لكل العمليات الحساسة
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class AuditEvent(UUIDMixin, Base):
    """حدث تدقيق — لا يُحذف ولا يُعدَّل."""
    __tablename__ = "audit_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # create | update | delete | approve | post | login | reject | void
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # clients | contracts | projects | invoices | ...
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_tenant_time", "tenant_id", "created_at"),
        Index("ix_audit_entity", "tenant_id", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.action} {self.entity_type}/{self.entity_id}>"
