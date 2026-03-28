"""
SARC360 ERP - Payroll Schemas
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PayrollBase(BaseModel):
    employee_id: uuid.UUID
    pay_period_start: date
    pay_period_end: date
    basic_salary_sar: Decimal = Field(..., ge=0)
    housing_allowance_sar: Decimal = Field(Decimal("0.00"), ge=0)
    transport_allowance_sar: Decimal = Field(Decimal("0.00"), ge=0)
    other_allowances_sar: Decimal = Field(Decimal("0.00"), ge=0)
    gosi_employee_sar: Decimal = Field(Decimal("0.00"), ge=0)
    gosi_employer_sar: Decimal = Field(Decimal("0.00"), ge=0)
    other_deductions_sar: Decimal = Field(Decimal("0.00"), ge=0)
    notes: str | None = None


class PayrollCreate(PayrollBase):
    pass


class PayrollUpdate(BaseModel):
    basic_salary_sar: Decimal | None = Field(None, ge=0)
    housing_allowance_sar: Decimal | None = Field(None, ge=0)
    transport_allowance_sar: Decimal | None = Field(None, ge=0)
    other_allowances_sar: Decimal | None = Field(None, ge=0)
    gosi_employee_sar: Decimal | None = Field(None, ge=0)
    gosi_employer_sar: Decimal | None = Field(None, ge=0)
    other_deductions_sar: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class PayrollApprove(BaseModel):
    approved_by: uuid.UUID


class PayrollMarkPaid(BaseModel):
    payment_date: date
    bank_transfer_ref: str | None = None
    wps_file_ref: str | None = None


class PayrollRead(PayrollBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payroll_number: str
    gross_salary_sar: Decimal
    net_salary_sar: Decimal
    status: str
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    payment_date: date | None = None
    bank_transfer_ref: str | None = None
    wps_file_ref: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None


class PayrollListResponse(BaseModel):
    items: list[PayrollRead]
    total: int
    page: int
    page_size: int
    pages: int
