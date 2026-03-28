"""
SARC360 ERP - Cost Engine Schemas
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PayRateBase(BaseModel):
    employee_id: uuid.UUID
    effective_from: date
    effective_to: date | None = None
    monthly_gross_salary: Decimal = Field(..., ge=0)
    employer_cost_rate: Decimal = Field(Decimal("0.0000"), ge=0)
    standard_monthly_hours: Decimal = Field(Decimal("240.00"), gt=0)
    overtime_multiplier: Decimal = Field(Decimal("1.5000"), ge=0)


class PayRateCreate(PayRateBase):
    pass


class PayRateUpdate(BaseModel):
    effective_to: date | None = None
    monthly_gross_salary: Decimal | None = Field(None, ge=0)
    employer_cost_rate: Decimal | None = Field(None, ge=0)
    standard_monthly_hours: Decimal | None = Field(None, gt=0)


class PayRateRead(PayRateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    hourly_cost: Decimal
    overtime_multiplier: Decimal
    created_at: datetime


class PayRateListResponse(BaseModel):
    items: list[PayRateRead]
    total: int


# ── Timesheet costing ─────────────────────────────────────────────────────────

class CostTimesheetRequest(BaseModel):
    timesheet_id: uuid.UUID
    employee_id: uuid.UUID
    work_date: date
    hours: Decimal = Field(..., gt=0)


class TimesheetCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    timesheet_id: uuid.UUID
    employee_rate_id: uuid.UUID
    hours: Decimal
    hourly_cost: Decimal
    cost_amount: Decimal
    costed_at: datetime
    costed_by: uuid.UUID | None
