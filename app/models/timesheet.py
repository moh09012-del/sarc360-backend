"""
SARC360 ERP - Timesheet Model
بطاقات الوقت مع approval workflow
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Timesheet(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "timesheets"

    # ── Identity ────────────────────────────────────────────────────────────
    timesheet_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="e.g. TS-001"
    )

    # ── Links ────────────────────────────────────────────────────────────────
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to employees.id"
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to projects.id"
    )

    # ── Period ───────────────────────────────────────────────────────────────
    week_start_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Monday of the work week"
    )

    # ── Daily Hours ──────────────────────────────────────────────────────────
    hours_sun: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))
    hours_mon: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))
    hours_tue: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))
    hours_wed: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))
    hours_thu: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))
    hours_fri: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))
    hours_sat: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.00"))

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Approval Workflow ────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft | submitted | approved | rejected"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to employees.id"
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Tenant isolation (Gate 2) ─────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to tenants.id"
    )

    # ── Audit ────────────────────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_timesheets_employee", "employee_id"),
        Index("ix_timesheets_project", "project_id"),
        Index("ix_timesheets_status", "status"),
        Index("ix_timesheets_week", "week_start_date"),
        Index("ix_timesheets_tenant", "tenant_id", "id"),
    )

    @property
    def total_hours(self) -> Decimal:
        return (
            self.hours_sun + self.hours_mon + self.hours_tue + self.hours_wed
            + self.hours_thu + self.hours_fri + self.hours_sat
        )

    def __repr__(self) -> str:
        return f"<Timesheet {self.timesheet_number} – {self.week_start_date}>"
