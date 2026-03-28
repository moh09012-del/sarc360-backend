"""
SARC360 ERP - Expense / Purchase Model
جدول المصروفات والمشتريات
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Expense(UUIDMixin, TimestampMixin, Base):
    """مصروف / مشتريات مرتبط بمشروع."""
    __tablename__ = "expenses"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    # FK إلى projects.id — لا نضع قيد FK هنا لتجنب تعقيدات الهجرة
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True
    )
    # po_id → FK إلى contracts.id (اختياري)
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=True
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    # subcontractor | materials | equipment | transport | other
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount_net: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    # amount_gross computed in Python: amount_net + vat_amount
    amount_gross: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    # draft | approved | posted | void
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    gl_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_expenses_project", "tenant_id", "project_id", "expense_date"),
        Index("ix_expenses_supplier", "tenant_id", "supplier_id"),
        CheckConstraint("amount_net >= 0", name="ck_expenses_amount_net"),
        CheckConstraint("vat_amount >= 0", name="ck_expenses_vat_amount"),
    )

    @property
    def computed_gross(self) -> Decimal:
        return self.amount_net + self.vat_amount

    def __repr__(self) -> str:
        return f"<Expense {self.category} – {self.amount_net} {self.currency}>"
