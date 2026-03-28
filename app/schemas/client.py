"""
SARC360 ERP - Client Schemas
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientBase(BaseModel):
    name_en: str = Field(..., min_length=1, max_length=300)
    name_ar: str | None = Field(None, max_length=300)
    cr_number: str | None = Field(None, max_length=50)
    vat_number: str | None = Field(None, max_length=50)
    billing_email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=30)
    address_line1: str | None = Field(None, max_length=400)
    city: str | None = Field(None, max_length=100)
    country: str = Field("SA", max_length=10)


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name_en: str | None = Field(None, min_length=1, max_length=300)
    name_ar: str | None = None
    cr_number: str | None = None
    vat_number: str | None = None
    billing_email: str | None = None
    phone: str | None = None
    address_line1: str | None = None
    city: str | None = None
    country: str | None = None
    is_active: bool | None = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseModel):
    items: list[ClientRead]
    total: int
    page: int
    page_size: int
    pages: int
