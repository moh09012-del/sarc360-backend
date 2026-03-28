"""
SARC360 ERP - Project Schemas
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name_en: str = Field(..., min_length=2, max_length=300)
    name_ar: str | None = Field(None, max_length=300)
    client_name: str = Field(..., min_length=2, max_length=300)
    client_id: uuid.UUID | None = None
    po_number: str | None = Field(None, max_length=100)
    po_id: uuid.UUID | None = None
    po_value_sar: Decimal = Field(Decimal("0.00"), ge=0)
    contract_value_sar: Decimal = Field(Decimal("0.00"), ge=0)
    start_date: date
    end_date: date | None = None
    department: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=200)
    description: str | None = None
    project_manager_id: uuid.UUID | None = None
    status: str = Field("active", description="active | completed | on_hold | cancelled")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name_en: str | None = Field(None, min_length=2, max_length=300)
    name_ar: str | None = None
    client_name: str | None = None
    client_id: uuid.UUID | None = None
    po_number: str | None = None
    po_id: uuid.UUID | None = None
    po_value_sar: Decimal | None = Field(None, ge=0)
    contract_value_sar: Decimal | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    department: str | None = None
    location: str | None = None
    description: str | None = None
    project_manager_id: uuid.UUID | None = None
    status: str | None = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_number: str
    tenant_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None


class ProjectListResponse(BaseModel):
    items: list[ProjectRead]
    total: int
    page: int
    page_size: int
    pages: int
