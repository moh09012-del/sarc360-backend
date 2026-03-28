"""
SARC360 ERP - Supplier Schemas
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SUPPLIER_TYPES = ("manpower", "equipment", "service", "materials", "other")


class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    supplier_type: str = Field(..., description="manpower | equipment | service | materials | other")
    vat_number: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=400)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    supplier_type: str | None = None
    vat_number: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool | None = None


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int
    pages: int
