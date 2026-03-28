"""
SARC360 ERP - Payroll Model
رواتب مع WPS/Mudad export
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class PayrollRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payroll_runs"

    # ── Identity ────────────────────────────────────────────────────────────
    payroll_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, comment="e.g. PAY-2026-03-001"
    )

    # ── Employee ─────────────────────────────────────────────────────────────
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to employees.id"
    )

    # ── Period ───────────────────────────────────────────────────────────────
    pay_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    pay_period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Earnings (SAR) ───────────────────────────────────────────────────────
    basic_salary_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    housing_allowance_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    transport_allowance_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    other_allowances_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    gross_salary_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # ── Deductions (SAR) ─────────────────────────────────────────────────────
    gosi_employee_sar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"),
        comment="9% employee GOSI (Saudi nationals)"
    )
    gosi_employer_sar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"),
        comment="10% employer GOSI contribution"
    )
    other_deductions_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    net_salary_sar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Approval ─────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft | approved | paid"
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── WPS / Mudad ──────────────────────────────────────────────────────────
    wps_file_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Mudad WPS file reference"
    )
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_transfer_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Tenant isolation (Gate 2) ─────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to tenants.id"
    )

    # ── Audit ────────────────────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_payroll_employee", "employee_id"),
        Index("ix_payroll_status", "status"),
        Index("ix_payroll_period", "pay_period_start", "pay_period_end"),
        Index("ix_payroll_tenant", "tenant_id", "id"),
    )

    def __repr__(self) -> str:
        return f"<PayrollRun {self.payroll_number} – {self.net_salary_sar} SAR>"
