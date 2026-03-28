"""
SARC360 ERP - Contract / PO Schemas
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ContractBase(BaseModel):
    client_id: uuid.UUID
    po_number: str = Field(..., min_length=1, max_length=100)
    title: str | None = Field(None, max_length=400)
    currency: str = Field("SAR", max_length=3)
    total_value: Decimal = Field(Decimal("0.00"), ge=0)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    title: str | None = Field(None, max_length=400)
    total_value: Decimal | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None  # draft | active | closed | cancelled
    notes: str | None = None


class ContractRead(ContractBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str
    remaining_value: Decimal = Decimal("0.00")
    created_at: datetime
    updated_at: datetime


class ContractListResponse(BaseModel):
    items: list[ContractRead]
    total: int
    page: int
    page_size: int
    pages: int


class ContractUtilizationResponse(BaseModel):
    id: uuid.UUID
    total_value: Decimal
    invoiced: Decimal
    remaining: Decimal
    percentage_used: Decimal

