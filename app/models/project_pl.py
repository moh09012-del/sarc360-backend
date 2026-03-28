"""
SARC360 ERP - Project P&L Period Snapshots
جداول ربحية المشروع بالفترات
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class ProjectPLPeriod(UUIDMixin, Base):
    """لقطة ربحية مشروع لفترة زمنية."""
    __tablename__ = "project_pl_periods"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    revenue_net: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    vendor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    overhead_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    # computed: revenue_net - labor_cost - vendor_cost
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    # computed: gross_profit - overhead_allocated
    net_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    billable_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    # computed: billable_hours / total_hours (if total_hours > 0)
    utilization_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=Decimal("0.0000"))

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    computed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "period_start", "period_end", name="ux_pl_period"),
        Index("ix_pl_project_period", "tenant_id", "project_id", "period_start", "period_end"),
    )

    def recompute(self) -> None:
        """احسب المشتقات وحدّث الحقول."""
        self.gross_profit = self.revenue_net - self.labor_cost - self.vendor_cost
        self.net_profit = self.gross_profit - self.overhead_allocated
        if self.total_hours and self.total_hours > 0:
            self.utilization_rate = round(self.billable_hours / self.total_hours, 4)
        else:
            self.utilization_rate = Decimal("0.0000")

    def __repr__(self) -> str:
        return f"<ProjectPL proj={self.project_id} {self.period_start}→{self.period_end}>"
