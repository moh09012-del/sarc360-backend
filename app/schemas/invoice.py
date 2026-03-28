"""
SARC360 ERP - Invoice Schemas
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvoiceBase(BaseModel):
    project_id: uuid.UUID | None = None
    po_id: uuid.UUID | None = None
    client_name: str = Field(..., min_length=2, max_length=300)
    invoice_date: date
    due_date: date | None = None
    subtotal_sar: Decimal = Field(..., ge=0)
    vat_rate: Decimal = Field(Decimal("0.1500"), ge=0, le=1)
    description: str | None = None

    @model_validator(mode="after")
    def compute_vat_and_total(self) -> "InvoiceBase":
        self.vat_amount_sar = (self.subtotal_sar * self.vat_rate).quantize(Decimal("0.01"))
        self.total_sar = self.subtotal_sar + self.vat_amount_sar
        return self

    vat_amount_sar: Decimal = Decimal("0.00")
    total_sar: Decimal = Decimal("0.00")


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    client_name: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal_sar: Decimal | None = Field(None, ge=0)
    description: str | None = None
    status: str | None = None
    payment_date: date | None = None
    payment_reference: str | None = None


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    project_id: uuid.UUID | None = None
    client_name: str
    invoice_date: date
    due_date: date | None = None
    subtotal_sar: Decimal
    vat_rate: Decimal
    vat_amount_sar: Decimal
    total_sar: Decimal
    description: str | None = None
    status: str
    payment_date: date | None = None
    payment_reference: str | None = None
    gl_posted: bool
    gl_posted_at: datetime | None = None
    gl_entry_ref: str | None = None
    zatca_status: str
    zatca_uuid: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None


class InvoiceListResponse(BaseModel):
    items: list[InvoiceRead]
    total: int
    page: int
    page_size: int
    pages: int
