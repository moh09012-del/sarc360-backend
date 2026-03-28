"""
SARC360 ERP - Dashboard + Project P&L Schemas
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ── Project P&L ───────────────────────────────────────────────────────────────

class PLPeriodCreate(BaseModel):
    project_id: uuid.UUID
    period_start: date
    period_end: date
    revenue_net: Decimal = Field(Decimal("0.00"), ge=0)
    labor_cost: Decimal = Field(Decimal("0.00"), ge=0)
    vendor_cost: Decimal = Field(Decimal("0.00"), ge=0)
    overhead_allocated: Decimal = Field(Decimal("0.00"), ge=0)
    billable_hours: Decimal = Field(Decimal("0.00"), ge=0)
    total_hours: Decimal = Field(Decimal("0.00"), ge=0)


class PLPeriodRead(PLPeriodCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    gross_profit: Decimal
    net_profit: Decimal
    utilization_rate: Decimal
    computed_at: datetime
    computed_by: uuid.UUID | None


# ── Dashboard ─────────────────────────────────────────────────────────────────

class TopClient(BaseModel):
    client_id: uuid.UUID | None
    client_name: str
    revenue_net: Decimal


class DashboardResponse(BaseModel):
    period_start: date
    period_end: date
    revenue_net: Decimal
    labor_cost: Decimal
    vendor_cost: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    utilization_rate: Decimal
    ar_outstanding: Decimal
    active_projects: int
    top_clients: list[TopClient]
