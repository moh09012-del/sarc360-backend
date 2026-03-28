"""
SARC360 ERP - Cost Engine Models
تكلفة الموظف بالساعة + ربط تكاليف التايم شيت
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class EmployeePayRate(UUIDMixin, Base):
    """معدل تكلفة الموظف بالساعة (نطاق تاريخي)."""
    __tablename__ = "employee_pay_rates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    # FK إلى employees.id
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, comment="NULL = مستمر")

    monthly_gross_salary: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    # نسبة تكلفة صاحب العمل (GOSI + بدلات): مثال 0.12
    employer_cost_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0.0000")
    )
    # ساعات معيارية/شهر (افتراضي 240)
    standard_monthly_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("240.00")
    )
    # عامل ساعات إضافي (overtime multiplier)
    overtime_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("1.5000")
    )
    # hourly_cost = (monthly_gross_salary * (1 + employer_cost_rate)) / standard_monthly_hours
    # محسوب ومخزن عند الإنشاء/التعديل
    hourly_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0.000000"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_employee_rates_lookup", "tenant_id", "employee_id", "effective_from", "effective_to"),
        CheckConstraint("monthly_gross_salary >= 0", name="ck_pay_rates_salary"),
        CheckConstraint("employer_cost_rate >= 0", name="ck_pay_rates_cost_rate"),
        CheckConstraint("standard_monthly_hours > 0", name="ck_pay_rates_hours"),
    )

    def compute_hourly_cost(self) -> Decimal:
        """احسب تكلفة الساعة وخزّنها."""
        if self.standard_monthly_hours and self.standard_monthly_hours > 0:
            rate = self.monthly_gross_salary * (1 + self.employer_cost_rate)
            self.hourly_cost = round(rate / self.standard_monthly_hours, 6)
        return self.hourly_cost

    @property
    def overtime_hourly_cost(self) -> Decimal:
        """تعويض ساعات إضافية العاملة بـ multiplier"""
        if self.overtime_multiplier and self.overtime_multiplier > 0:
            return round(self.hourly_cost * self.overtime_multiplier, 6)
        return self.hourly_cost

    def __repr__(self) -> str:
        return f"<EmployeePayRate employee={self.employee_id} from={self.effective_from}>"


class TimesheetCost(UUIDMixin, Base):
    """تكلفة التايم شيت — سجل محسوب لا يتغير (immutable)."""
    __tablename__ = "timesheet_costs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    # FK إلى timesheets.id
    timesheet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_rate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_pay_rates.id", ondelete="RESTRICT"), nullable=False
    )
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    hourly_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    costed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    costed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "timesheet_id", name="ux_timesheet_costs_timesheet"),
        CheckConstraint("hours >= 0", name="ck_ts_costs_hours"),
        CheckConstraint("cost_amount >= 0", name="ck_ts_costs_amount"),
    )

    def __repr__(self) -> str:
        return f"<TimesheetCost ts={self.timesheet_id} cost={self.cost_amount}>"
