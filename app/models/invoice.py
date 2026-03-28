"""
SARC360 ERP - Invoice Model
فواتير مع GL auto-post وZATCA Phase 2
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Invoice(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    # ── Identity ────────────────────────────────────────────────────────────
    invoice_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, comment="e.g. INV-2026-001"
    )

    # ── Tenant isolation (Gate 2) ─────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to tenants.id"
    )

    # ── Links ────────────────────────────────────────────────────────────────
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to projects.id"
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to contracts.id"
    )
    client_name: Mapped[str] = mapped_column(String(300), nullable=False)

    # ── Dates ────────────────────────────────────────────────────────────────
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Amounts (SAR) ────────────────────────────────────────────────────────
    subtotal_sar: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.1500"),
        comment="15% KSA VAT"
    )
    vat_amount_sar: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    total_sar: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Status ───────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft | sent | paid | overdue | cancelled"
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── GL Auto-Post ─────────────────────────────────────────────────────────
    gl_posted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gl_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gl_entry_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Journal entry reference"
    )

    # ── ZATCA Phase 2 ────────────────────────────────────────────────────────
    zatca_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | submitted | approved | rejected"
    )
    zatca_uuid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zatca_hash: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Audit ────────────────────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_project", "project_id"),
        Index("ix_invoices_due_date", "due_date"),
        Index("ix_invoices_zatca_status", "zatca_status"),
        Index("ix_invoices_tenant", "tenant_id", "id"),
        Index("ix_invoices_po", "tenant_id", "po_id"),
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} – {self.total_sar} SAR>"
