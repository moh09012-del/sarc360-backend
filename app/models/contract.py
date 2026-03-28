"""
SARC360 ERP - Contract / Purchase Order Model
جدول العقود وأوامر الشراء
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Contract(UUIDMixin, TimestampMixin, Base):
    """عقد أو أمر شراء (PO) مرتبط بعميل."""
    __tablename__ = "contracts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    po_number: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    total_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # draft | active | closed | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", "po_number", name="ux_contracts_po_per_client"),
        Index("ix_contracts_tenant", "tenant_id", "id"),
        Index("ix_contracts_client", "tenant_id", "client_id"),
        CheckConstraint("total_value >= 0", name="ck_contracts_total_value"),
    )

    def __repr__(self) -> str:
        return f"<Contract {self.po_number} – {self.total_value} {self.currency}>"
