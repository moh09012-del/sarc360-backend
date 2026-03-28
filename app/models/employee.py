"""
SARC360 ERP - Employee Model
جدول الموظفين - شركة سما الروابي للمقاولات

Covers all fields required for:
  - Saudi Labor Law compliance
  - GOSI enrollment
  - WPS/Mudad payroll transfers
  - Iqama/passport expiry alerts
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


# ── Enums ──────────────────────────────────────────────────────────────────────
class EmploymentType(str, PyEnum):
    internal = "internal"           # On payroll


class EmployeeStatus(str, PyEnum):
    active = "active"
    on_leave = "on_leave"
    terminated = "terminated"
    suspended = "suspended"


class Department(str, PyEnum):
    operations = "operations"
    hse = "hse"
    finance = "finance"
    hr = "hr"
    engineering = "engineering"
    procurement = "procurement"
    it = "it"
    management = "management"


# ── Model ──────────────────────────────────────────────────────────────────────
class Employee(UUIDMixin, TimestampMixin, Base):
    """
    Internal employee (on payroll).
    Outsourced workers are in a separate table — they are AP cost, not payroll.
    """

    __tablename__ = "employees"

    # ── Identity ────────────────────────────────────────────────────────────
    employee_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="e.g. EMP-001"
    )
    full_name_en: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Full name in English"
    )
    full_name_ar: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="الاسم الكامل بالعربية"
    )

    # ── Saudi / Expat Documents ──────────────────────────────────────────────
    nationality: Mapped[str] = mapped_column(
        String(60), nullable=False, comment="Saudi, Indian, Pakistani, Yemeni, ..."
    )
    iqama_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        comment="10-digit: starts with 1 (Saudi) or 2 (expat)",
    )
    iqama_expiry_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Drives 90/60/30-day alert task"
    )
    passport_number: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    passport_expiry_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    # ── Job Info ─────────────────────────────────────────────────────────────
    job_title: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="HSE Supervisor, Site Engineer, Project Manager, ..."
    )
    department: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    employment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EmploymentType.internal.value,
    )

    # ── Dates ────────────────────────────────────────────────────────────────
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    probation_end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="90 days standard per Saudi Labor Law"
    )
    contract_end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="NULL = open-ended contract"
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Compensation (SAR) ───────────────────────────────────────────────────
    basic_salary_sar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    housing_allowance_sar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"),
        comment="Standard KSA housing allowance component"
    )
    transport_allowance_sar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    other_allowances_sar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    # ── GOSI ─────────────────────────────────────────────────────────────────
    gosi_enrolled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Mandatory for Saudi nationals, voluntary for expats",
    )
    gosi_number: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="GOSI registration number"
    )

    # ── Banking (WPS/Mudad) ──────────────────────────────────────────────────
    saudi_iban: Mapped[str | None] = mapped_column(
        String(34),
        nullable=True,
        comment="SA + 22 digits — validated on write",
    )
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="SNB, Al Rajhi, Riyad Bank, ...",
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EmployeeStatus.active.value,
    )
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # ── Tenant isolation (Gate 2) ─────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to tenants.id"
    )

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User UUID who created this record",
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_employees_status", "status"),
        Index("ix_employees_iqama_expiry", "iqama_expiry_date"),
        Index("ix_employees_nationality", "nationality"),
        Index("ix_employees_department", "department"),
        Index("ix_employees_tenant", "tenant_id", "id"),
    )

    def __repr__(self) -> str:
        return f"<Employee {self.employee_number} – {self.full_name_en}>"

    @property
    def gross_salary_sar(self) -> Decimal:
        """Total gross before GOSI and deductions."""
        return (
            self.basic_salary_sar
            + self.housing_allowance_sar
            + self.transport_allowance_sar
            + self.other_allowances_sar
        )
