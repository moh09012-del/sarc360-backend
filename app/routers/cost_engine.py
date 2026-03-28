"""
SARC360 ERP - Cost Engine Router
GET    /api/v1/pay-rates
POST   /api/v1/pay-rates
GET    /api/v1/pay-rates/{id}
PATCH  /api/v1/pay-rates/{id}
GET    /api/v1/pay-rates/employee/{employee_id}/current   — get_employee_hourly_cost()
POST   /api/v1/timesheets/cost                            — cost_timesheet()
GET    /api/v1/timesheets/{timesheet_id}/cost
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select

from app.core.deps import AuthUser, DbSession
from app.models.cost_engine import EmployeePayRate, TimesheetCost
from app.schemas.cost_engine import (
    CostTimesheetRequest,
    PayRateCreate,
    PayRateListResponse,
    PayRateRead,
    PayRateUpdate,
    TimesheetCostRead,
)
from app.services.audit import log_event

router = APIRouter(tags=["Cost Engine"])


# ─────────────────────────────────────────────────────────────────────────────
# Pay Rates CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pay-rates", response_model=PayRateListResponse, summary="List pay rates")
async def list_pay_rates(
    cu: AuthUser,
    db: DbSession,
    employee_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(False),
) -> PayRateListResponse:
    q = select(EmployeePayRate).where(EmployeePayRate.tenant_id == cu.tenant_id)
    if employee_id:
        q = q.where(EmployeePayRate.employee_id == employee_id)
    if active_only:
        today = date.today()
        q = q.where(
            EmployeePayRate.effective_from <= today,
            or_(EmployeePayRate.effective_to.is_(None), EmployeePayRate.effective_to >= today),
        )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.order_by(EmployeePayRate.effective_from.desc()))).scalars().all()
    return PayRateListResponse(items=[PayRateRead.model_validate(r) for r in rows], total=total)


@router.post("/pay-rates", response_model=PayRateRead, status_code=status.HTTP_201_CREATED, summary="Create pay rate")
async def create_pay_rate(payload: PayRateCreate, cu: AuthUser, db: DbSession) -> PayRateRead:
    cu.require_role("super_admin", "finance_hr")

    obj = EmployeePayRate(tenant_id=cu.tenant_id, **payload.model_dump())
    obj.compute_hourly_cost()
    db.add(obj)
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="employee_pay_rates", entity_id=obj.id,
                    after_data=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(obj)
    return PayRateRead.model_validate(obj)


@router.get("/pay-rates/employee/{employee_id}/current", response_model=PayRateRead,
            summary="Get current hourly cost for an employee")
async def get_employee_hourly_cost(
    employee_id: uuid.UUID, cu: AuthUser, db: DbSession,
    as_of: date = Query(default_factory=date.today),
) -> PayRateRead:
    """Returns the effective pay rate for `employee_id` on `as_of` date."""
    res = await db.execute(
        select(EmployeePayRate)
        .where(
            EmployeePayRate.tenant_id == cu.tenant_id,
            EmployeePayRate.employee_id == employee_id,
            EmployeePayRate.effective_from <= as_of,
            or_(EmployeePayRate.effective_to.is_(None), EmployeePayRate.effective_to >= as_of),
        )
        .order_by(EmployeePayRate.effective_from.desc())
        .limit(1)
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active pay rate for employee {employee_id} on {as_of}.",
        )
    return PayRateRead.model_validate(obj)


@router.get("/pay-rates/{rate_id}", response_model=PayRateRead, summary="Get pay rate")
async def get_pay_rate(rate_id: uuid.UUID, cu: AuthUser, db: DbSession) -> PayRateRead:
    res = await db.execute(
        select(EmployeePayRate).where(
            EmployeePayRate.id == rate_id, EmployeePayRate.tenant_id == cu.tenant_id
        )
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pay rate not found.")
    return PayRateRead.model_validate(obj)


@router.patch("/pay-rates/{rate_id}", response_model=PayRateRead, summary="Update pay rate")
async def update_pay_rate(
    rate_id: uuid.UUID, payload: PayRateUpdate, cu: AuthUser, db: DbSession
) -> PayRateRead:
    cu.require_role("super_admin", "finance_hr")
    res = await db.execute(
        select(EmployeePayRate).where(
            EmployeePayRate.id == rate_id, EmployeePayRate.tenant_id == cu.tenant_id
        )
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pay rate not found.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    obj.compute_hourly_cost()

    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="update", entity_type="employee_pay_rates", entity_id=obj.id,
                    after_data=payload.model_dump(mode="json", exclude_none=True))
    await db.commit()
    await db.refresh(obj)
    return PayRateRead.model_validate(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Timesheet Costing
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/timesheets/cost", response_model=TimesheetCostRead, status_code=status.HTTP_201_CREATED,
             summary="Cost a timesheet (cost_timesheet)")
async def cost_timesheet(payload: CostTimesheetRequest, cu: AuthUser, db: DbSession) -> TimesheetCostRead:
    """
    Find the effective pay rate for employee on work_date and compute cost.
    Unique constraint prevents double-costing the same timesheet.
    """
    cu.require_role("super_admin", "finance_hr")

    # Check idempotency
    existing = await db.execute(
        select(TimesheetCost).where(
            TimesheetCost.tenant_id == cu.tenant_id,
            TimesheetCost.timesheet_id == payload.timesheet_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Timesheet {payload.timesheet_id} is already costed.",
        )

    # Get pay rate
    rate_res = await db.execute(
        select(EmployeePayRate)
        .where(
            EmployeePayRate.tenant_id == cu.tenant_id,
            EmployeePayRate.employee_id == payload.employee_id,
            EmployeePayRate.effective_from <= payload.work_date,
            or_(EmployeePayRate.effective_to.is_(None), EmployeePayRate.effective_to >= payload.work_date),
        )
        .order_by(EmployeePayRate.effective_from.desc())
        .limit(1)
    )
    rate = rate_res.scalar_one_or_none()
    if not rate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No pay rate for employee {payload.employee_id} on {payload.work_date}.",
        )

    cost_amount = round(payload.hours * rate.hourly_cost, 2)
    tc = TimesheetCost(
        tenant_id=cu.tenant_id,
        timesheet_id=payload.timesheet_id,
        employee_rate_id=rate.id,
        hours=payload.hours,
        hourly_cost=rate.hourly_cost,
        cost_amount=cost_amount,
        costed_at=datetime.now(tz=timezone.utc),
        costed_by=cu.user_id,
    )
    db.add(tc)
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="timesheet_costs", entity_id=tc.id,
                    after_data={"timesheet_id": str(payload.timesheet_id), "cost_amount": str(cost_amount)})
    await db.commit()
    await db.refresh(tc)
    return TimesheetCostRead.model_validate(tc)


@router.get("/timesheets/{timesheet_id}/cost", response_model=TimesheetCostRead, summary="Get timesheet cost")
async def get_timesheet_cost(timesheet_id: uuid.UUID, cu: AuthUser, db: DbSession) -> TimesheetCostRead:
    res = await db.execute(
        select(TimesheetCost).where(
            TimesheetCost.tenant_id == cu.tenant_id,
            TimesheetCost.timesheet_id == timesheet_id,
        )
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet cost not found.")
    return TimesheetCostRead.model_validate(obj)
