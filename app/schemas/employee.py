"""
SARC360 ERP - Employee Pydantic Schemas (request / response)
"""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Validators ─────────────────────────────────────────────────────────────────
def _validate_iqama(v: str | None) -> str | None:
    if v is None:
        return v
    if not re.fullmatch(r"[12]\d{9}", v):
        raise ValueError(
            "Iqama number must be 10 digits starting with 1 (Saudi) or 2 (expat)"
        )
    return v


def _validate_saudi_iban(v: str | None) -> str | None:
    if v is None:
        return v
    clean = v.replace(" ", "").upper()
    if not re.fullmatch(r"SA\d{22}", clean):
        raise ValueError("Saudi IBAN must be SA + 22 digits (total 24 chars)")
    return clean


# ── Base (shared fields) ───────────────────────────────────────────────────────
class EmployeeBase(BaseModel):
    full_name_en: str = Field(..., min_length=2, max_length=200)
    full_name_ar: str | None = Field(None, max_length=200)
    nationality: str = Field(..., max_length=60)
    iqama_number: str | None = Field(None)
    iqama_expiry_date: date | None = None
    passport_number: str | None = Field(None, max_length=30)
    passport_expiry_date: date | None = None
    job_title: str = Field(..., max_length=100)
    department: str | None = Field(None, max_length=100)
    hire_date: date
    probation_end_date: date | None = None
    contract_end_date: date | None = None
    date_of_birth: date | None = None
    basic_salary_sar: Decimal = Field(Decimal("0.00"), ge=0)
    housing_allowance_sar: Decimal = Field(Decimal("0.00"), ge=0)
    transport_allowance_sar: Decimal = Field(Decimal("0.00"), ge=0)
    other_allowances_sar: Decimal = Field(Decimal("0.00"), ge=0)
    gosi_enrolled: bool = False
    gosi_number: str | None = Field(None, max_length=30)
    saudi_iban: str | None = None
    bank_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=200)

    @field_validator("iqama_number")
    @classmethod
    def validate_iqama(cls, v: str | None) -> str | None:
        return _validate_iqama(v)

    @field_validator("saudi_iban")
    @classmethod
    def validate_iban(cls, v: str | None) -> str | None:
        return _validate_saudi_iban(v)


# ── Create ─────────────────────────────────────────────────────────────────────
class EmployeeCreate(EmployeeBase):
    """Payload for POST /api/v1/employees"""
    pass


# ── Update (all fields optional) ──────────────────────────────────────────────
class EmployeeUpdate(BaseModel):
    """Payload for PATCH /api/v1/employees/{id} — all fields optional."""

    full_name_en: str | None = Field(None, min_length=2, max_length=200)
    full_name_ar: str | None = None
    nationality: str | None = None
    iqama_number: str | None = None
    iqama_expiry_date: date | None = None
    passport_number: str | None = None
    passport_expiry_date: date | None = None
    job_title: str | None = None
    department: str | None = None
    hire_date: date | None = None
    probation_end_date: date | None = None
    contract_end_date: date | None = None
    basic_salary_sar: Decimal | None = Field(None, ge=0)
    housing_allowance_sar: Decimal | None = Field(None, ge=0)
    transport_allowance_sar: Decimal | None = Field(None, ge=0)
    other_allowances_sar: Decimal | None = Field(None, ge=0)
    gosi_enrolled: bool | None = None
    gosi_number: str | None = None
    saudi_iban: str | None = None
    bank_name: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None

    @field_validator("iqama_number")
    @classmethod
    def validate_iqama(cls, v: str | None) -> str | None:
        return _validate_iqama(v)

    @field_validator("saudi_iban")
    @classmethod
    def validate_iban(cls, v: str | None) -> str | None:
        return _validate_saudi_iban(v)


# ── Read (response) ────────────────────────────────────────────────────────────
class EmployeeRead(EmployeeBase):
    """Response schema — includes server-generated fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_number: str
    employment_type: str
    status: str
    gross_salary_sar: Decimal
    termination_date: date | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None


# ── Paginated list response ────────────────────────────────────────────────────
class EmployeeListResponse(BaseModel):
    items: list[EmployeeRead]
    total: int
    page: int
    page_size: int
    pages: int
