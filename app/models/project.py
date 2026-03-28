"""
SARC360 ERP - Project Model
جدول المشاريع - PO-as-Project
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    # ── Identity ────────────────────────────────────────────────────────────
    project_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="e.g. PRJ-001"
    )
    name_en: Mapped[str] = mapped_column(String(300), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ── Tenant isolation (Gate 2) ─────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="FK to tenants.id"
    )

    # ── Client / PO ──────────────────────────────────────────────────────────
    client_name: Mapped[str] = mapped_column(String(300), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to clients.id"
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to contracts.id"
    )
    po_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Purchase Order number"
    )
    po_value_sar: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    contract_value_sar: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )

    # ── Dates ────────────────────────────────────────────────────────────────
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Classification ───────────────────────────────────────────────────────
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── People ───────────────────────────────────────────────────────────────
    project_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to employees.id"
    )

    # ── Status ───────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active | completed | on_hold | cancelled"
    )

    # ── Audit ────────────────────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_projects_status", "status"),
        Index("ix_projects_client", "client_name"),
        Index("ix_projects_po_number", "po_number"),
        Index("ix_projects_tenant", "tenant_id", "id"),
        Index("ix_projects_client_id", "tenant_id", "client_id"),
        Index("ix_projects_po_id", "tenant_id", "po_id"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.project_number} – {self.name_en}>"
