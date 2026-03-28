"""
SARC360 ERP - Supplier Model
جدول الموردين / المقاولين من الباطن
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Supplier(UUIDMixin, TimestampMixin, Base):
    """مورد أو مقاول من الباطن."""
    __tablename__ = "suppliers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    # manpower | equipment | service | materials | other
    supplier_type: Mapped[str] = mapped_column(String(30), nullable=False)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="ux_suppliers_name_per_tenant"),
        Index("ix_suppliers_tenant", "tenant_id", "id"),
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.name} [{self.supplier_type}]>"
