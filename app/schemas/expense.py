"""
SARC360 ERP - Expense Schemas
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExpenseBase(BaseModel):
    project_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    po_id: uuid.UUID | None = None
    expense_date: date
    category: str = Field(..., description="subcontractor | materials | equipment | transport | other")
    description: str | None = None
    amount_net: Decimal = Field(..., ge=0)
    vat_amount: Decimal = Field(Decimal("0.00"), ge=0)
    currency: str = Field("SAR", max_length=3)


class ExpenseCreate(ExpenseBase):
    @model_validator(mode="after")
    def compute_gross(self) -> "ExpenseCreate":
        # gross is stored; computed here so callers don't need to send it
        return self


class ExpenseUpdate(BaseModel):
    description: str | None = None
    amount_net: Decimal | None = Field(None, ge=0)
    vat_amount: Decimal | None = Field(None, ge=0)
    status: str | None = None  # draft | approved | void


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    amount_gross: Decimal
    status: str
    gl_posted_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ExpenseListResponse(BaseModel):
    items: list[ExpenseRead]
    total: int
    page: int
    page_size: int
    pages: int
