"""
SARC360 ERP - Timesheet Schemas
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimesheetBase(BaseModel):
    employee_id: uuid.UUID
    project_id: uuid.UUID
    week_start_date: date
    hours_sun: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    hours_mon: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    hours_tue: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    hours_wed: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    hours_thu: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    hours_fri: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    hours_sat: Decimal = Field(Decimal("0.00"), ge=0, le=24)
    notes: str | None = None


class TimesheetCreate(TimesheetBase):
    pass


class TimesheetUpdate(BaseModel):
    hours_sun: Decimal | None = Field(None, ge=0, le=24)
    hours_mon: Decimal | None = Field(None, ge=0, le=24)
    hours_tue: Decimal | None = Field(None, ge=0, le=24)
    hours_wed: Decimal | None = Field(None, ge=0, le=24)
    hours_thu: Decimal | None = Field(None, ge=0, le=24)
    hours_fri: Decimal | None = Field(None, ge=0, le=24)
    hours_sat: Decimal | None = Field(None, ge=0, le=24)
    notes: str | None = None


class TimesheetApprove(BaseModel):
    approved_by: uuid.UUID


class TimesheetReject(BaseModel):
    rejection_reason: str = Field(..., min_length=5)


class TimesheetRead(TimesheetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timesheet_number: str
    total_hours: Decimal
    status: str
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TimesheetListResponse(BaseModel):
    items: list[TimesheetRead]
    total: int
    page: int
    page_size: int
    pages: int
