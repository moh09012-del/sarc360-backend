"""
SARC360 ERP - Client Model
جدول العملاء (B2B)
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Client(UUIDMixin, TimestampMixin, Base):
    """عميل (شركة أو جهة حكومية)."""
    __tablename__ = "clients"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    name_en: Mapped[str] = mapped_column(String(300), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cr_number: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="Commercial Registration")
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(400), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="SA")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name_en", name="ux_clients_name_per_tenant"),
        Index("ix_clients_tenant", "tenant_id", "id"),
    )

    def __repr__(self) -> str:
        return f"<Client {self.name_en}>"
