"""
SARC360 ERP — Timesheet Approval Workflow Service
تدفق الموافقة على بطاقات الوقت
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timesheet import Timesheet
from app.models.cost_engine import TimesheetCost, EmployeePayRate
from app.models.employee import Employee
from app.services.audit import log_event


async def submit_timesheet(
    db: AsyncSession,
    timesheet_id: uuid.UUID,
    tenant_id: uuid.UUID,
    submitted_by: uuid.UUID,
    request=None,
) -> Timesheet:
    """Submit timesheet from draft → submitted state."""
    result = await db.execute(
        select(Timesheet).where(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id,
        )
    )
    ts = result.scalar_one_or_none()
    if not ts:
        raise ValueError("Timesheet not found")
    if ts.status != "draft":
        raise ValueError(f"Cannot submit timesheet in {ts.status} state")

    ts.status = "submitted"
    ts.submitted_at = datetime.now(tz=timezone.utc)
    await db.flush()

    await log_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=submitted_by,
        action="submit",
        entity_type="timesheets",
        entity_id=timesheet_id,
        ip_address=request.client.host if request else None,
    )
    return ts


async def approve_timesheet(
    db: AsyncSession,
    timesheet_id: uuid.UUID,
    tenant_id: uuid.UUID,
    approved_by: uuid.UUID,
    request=None,
) -> Timesheet:
    """Approve timesheet → approved state and trigger cost calculation."""
    result = await db.execute(
        select(Timesheet).where(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id,
        )
    )
    ts = result.scalar_one_or_none()
    if not ts:
        raise ValueError("Timesheet not found")
    if ts.status not in ("draft", "submitted"):
        raise ValueError(f"Cannot approve timesheet in {ts.status} state")

    ts.status = "approved"
    ts.approved_at = datetime.now(tz=timezone.utc)
    ts.approved_by = approved_by
    await db.flush()

    # Automatically calculate costs
    await calculate_timesheet_cost(db, ts, tenant_id, approved_by)

    await log_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=approved_by,
        action="approve",
        entity_type="timesheets",
        entity_id=timesheet_id,
        ip_address=request.client.host if request else None,
    )
    return ts


async def reject_timesheet(
    db: AsyncSession,
    timesheet_id: uuid.UUID,
    tenant_id: uuid.UUID,
    rejection_reason: str,
    rejected_by: uuid.UUID,
    request=None,
) -> Timesheet:
    """Reject timesheet back to draft with reason."""
    result = await db.execute(
        select(Timesheet).where(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == tenant_id,
        )
    )
    ts = result.scalar_one_or_none()
    if not ts:
        raise ValueError("Timesheet not found")
    if ts.status != "submitted":
        raise ValueError(f"Cannot reject timesheet in {ts.status} state")

    ts.status = "draft"
    ts.rejection_reason = rejection_reason
    await db.flush()

    await log_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=rejected_by,
        action="reject",
        entity_type="timesheets",
        entity_id=timesheet_id,
        ip_address=request.client.host if request else None,
    )
    return ts


async def calculate_timesheet_cost(
    db: AsyncSession,
    timesheet: Timesheet,
    tenant_id: uuid.UUID,
    costed_by: uuid.UUID,
) -> TimesheetCost:
    """Calculate hourly cost for timesheet based on employee hourly rate."""
    # Get employee
    result = await db.execute(
        select(Employee).where(Employee.id == timesheet.employee_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise ValueError(f"Employee {timesheet.employee_id} not found")

    # Get effective hourly rate
    rate_result = await db.execute(
        select(EmployeePayRate).where(
            EmployeePayRate.tenant_id == tenant_id,
            EmployeePayRate.employee_id == timesheet.employee_id,
            EmployeePayRate.effective_from <= timesheet.week_start_date,
        ).order_by(EmployeePayRate.effective_from.desc())
    )
    rate = rate_result.scalar_one_or_none()
    if not rate:
        raise ValueError(
            f"No pay rate found for employee {emp.employee_number} on {timesheet.week_start_date}"
        )

    # Calculate total hours and cost
    total_hours = timesheet.total_hours
    hourly_cost = rate.hourly_cost

    cost_amount = total_hours * hourly_cost

    # Create/update timesheet cost record
    existing_result = await db.execute(
        select(TimesheetCost).where(
            TimesheetCost.tenant_id == tenant_id,
            TimesheetCost.timesheet_id == timesheet.id,
        )
    )
    ts_cost = existing_result.scalar_one_or_none()

    if ts_cost:
        ts_cost.hours = total_hours
        ts_cost.hourly_cost = hourly_cost
        ts_cost.cost_amount = cost_amount
        ts_cost.costed_by = costed_by
    else:
        ts_cost = TimesheetCost(
            tenant_id=tenant_id,
            timesheet_id=timesheet.id,
            employee_rate_id=rate.id,
            hours=total_hours,
            hourly_cost=hourly_cost,
            cost_amount=cost_amount,
            costed_by=costed_by,
        )
        db.add(ts_cost)

    await db.flush()
    return ts_cost
