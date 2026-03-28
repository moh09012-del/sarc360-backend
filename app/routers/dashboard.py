"""
SARC360 ERP - Project P&L + Dashboard Router
GET  /api/v1/dashboard?start=&end=
POST /api/v1/pl-periods
GET  /api/v1/pl-periods?project_id=
GET  /api/v1/pl-periods/{id}
"""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import AuthUser, DbSession
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.project_pl import ProjectPLPeriod
from app.schemas.dashboard import DashboardResponse, PLPeriodCreate, PLPeriodRead, TopClient
from app.services.audit import log_event

router = APIRouter(tags=["Dashboard / P&L"])


# ── Project P&L periods ───────────────────────────────────────────────────────

@router.post("/pl-periods", response_model=PLPeriodRead, status_code=status.HTTP_201_CREATED,
             summary="Create / upsert a P&L snapshot for a project period")
async def create_pl_period(payload: PLPeriodCreate, cu: AuthUser, db: DbSession) -> PLPeriodRead:
    cu.require_role("super_admin", "finance_hr", "projects")

    # Upsert: if same period exists, update it
    existing_res = await db.execute(
        select(ProjectPLPeriod).where(
            ProjectPLPeriod.tenant_id == cu.tenant_id,
            ProjectPLPeriod.project_id == payload.project_id,
            ProjectPLPeriod.period_start == payload.period_start,
            ProjectPLPeriod.period_end == payload.period_end,
        )
    )
    obj = existing_res.scalar_one_or_none()

    if obj:
        for field, value in payload.model_dump().items():
            setattr(obj, field, value)
        obj.computed_by = cu.user_id
    else:
        obj = ProjectPLPeriod(
            tenant_id=cu.tenant_id,
            computed_by=cu.user_id,
            **payload.model_dump(),
        )
        db.add(obj)

    obj.recompute()
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="project_pl_periods", entity_id=obj.id)
    await db.commit()
    await db.refresh(obj)
    return PLPeriodRead.model_validate(obj)


@router.get("/pl-periods", response_model=list[PLPeriodRead], summary="List P&L periods")
async def list_pl_periods(
    cu: AuthUser, db: DbSession,
    project_id: uuid.UUID | None = Query(None),
) -> list[PLPeriodRead]:
    q = select(ProjectPLPeriod).where(ProjectPLPeriod.tenant_id == cu.tenant_id)
    if project_id:
        q = q.where(ProjectPLPeriod.project_id == project_id)
    rows = (await db.execute(q.order_by(ProjectPLPeriod.period_start.desc()))).scalars().all()
    return [PLPeriodRead.model_validate(r) for r in rows]


@router.get("/pl-periods/{period_id}", response_model=PLPeriodRead, summary="Get P&L period")
async def get_pl_period(period_id: uuid.UUID, cu: AuthUser, db: DbSession) -> PLPeriodRead:
    res = await db.execute(
        select(ProjectPLPeriod).where(
            ProjectPLPeriod.id == period_id, ProjectPLPeriod.tenant_id == cu.tenant_id
        )
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="P&L period not found.")
    return PLPeriodRead.model_validate(obj)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardResponse, summary="Executive dashboard")
async def get_dashboard(
    cu: AuthUser,
    db: DbSession,
    start: date = Query(..., description="Period start date (YYYY-MM-DD)"),
    end: date = Query(..., description="Period end date (YYYY-MM-DD)"),
) -> DashboardResponse:
    tid = cu.tenant_id

    # Aggregate P&L periods in range
    pl_agg = await db.execute(
        select(
            func.coalesce(func.sum(ProjectPLPeriod.revenue_net), Decimal("0")).label("revenue_net"),
            func.coalesce(func.sum(ProjectPLPeriod.labor_cost), Decimal("0")).label("labor_cost"),
            func.coalesce(func.sum(ProjectPLPeriod.vendor_cost), Decimal("0")).label("vendor_cost"),
            func.coalesce(func.sum(ProjectPLPeriod.gross_profit), Decimal("0")).label("gross_profit"),
            func.coalesce(func.sum(ProjectPLPeriod.net_profit), Decimal("0")).label("net_profit"),
            func.coalesce(func.sum(ProjectPLPeriod.billable_hours), Decimal("0")).label("billable_hours"),
            func.coalesce(func.sum(ProjectPLPeriod.total_hours), Decimal("0")).label("total_hours"),
        ).where(
            ProjectPLPeriod.tenant_id == tid,
            ProjectPLPeriod.period_start >= start,
            ProjectPLPeriod.period_end <= end,
        )
    )
    pl = pl_agg.one()
    total_hours = pl.total_hours or Decimal("0")
    billable_hours = pl.billable_hours or Decimal("0")
    utilization = round(billable_hours / total_hours, 4) if total_hours > 0 else Decimal("0")

    # AR Outstanding = sum of sent/overdue invoices
    ar_res = await db.execute(
        select(func.coalesce(func.sum(Invoice.total_sar), Decimal("0"))).where(
            Invoice.tenant_id == tid,
            Invoice.invoice_date >= start,
            Invoice.invoice_date <= end,
            Invoice.status.in_(["sent", "overdue"]),
        )
    )
    ar_outstanding = ar_res.scalar_one()

    # Active projects count
    ap_res = await db.execute(
        select(func.count(Project.id)).where(
            Project.tenant_id == tid,
            Project.status == "active",
        )
    )
    active_projects = ap_res.scalar_one()

    # Top clients by revenue (from P&L project_id → project.client_id → client)
    top_res = await db.execute(
        select(
            ProjectPLPeriod.project_id,
            func.sum(ProjectPLPeriod.revenue_net).label("revenue"),
        )
        .where(
            ProjectPLPeriod.tenant_id == tid,
            ProjectPLPeriod.period_start >= start,
            ProjectPLPeriod.period_end <= end,
        )
        .group_by(ProjectPLPeriod.project_id)
        .order_by(func.sum(ProjectPLPeriod.revenue_net).desc())
        .limit(5)
    )
    top_rows = top_res.all()

    top_clients: list[TopClient] = []
    for row in top_rows:
        # Lookup client via project
        proj_res = await db.execute(
            select(Project.client_id, Project.client_name).where(
                Project.id == row.project_id, Project.tenant_id == tid
            )
        )
        proj = proj_res.one_or_none()
        client_name = "Unknown"
        client_id = None
        if proj:
            client_id = proj.client_id
            if proj.client_id:
                cli_res = await db.execute(
                    select(Client.name_en).where(Client.id == proj.client_id, Client.tenant_id == tid)
                )
                cli = cli_res.scalar_one_or_none()
                client_name = cli or proj.client_name
            else:
                client_name = proj.client_name

        top_clients.append(TopClient(
            client_id=client_id,
            client_name=client_name,
            revenue_net=row.revenue or Decimal("0"),
        ))

    return DashboardResponse(
        period_start=start,
        period_end=end,
        revenue_net=pl.revenue_net,
        labor_cost=pl.labor_cost,
        vendor_cost=pl.vendor_cost,
        gross_profit=pl.gross_profit,
        net_profit=pl.net_profit,
        utilization_rate=utilization,
        ar_outstanding=ar_outstanding,
        active_projects=active_projects,
        top_clients=top_clients,
    )
