"""
SARC360 ERP - Timesheets Router
GET    /api/v1/timesheets
POST   /api/v1/timesheets
GET    /api/v1/timesheets/{id}
PATCH  /api/v1/timesheets/{id}
POST   /api/v1/timesheets/{id}/submit
POST   /api/v1/timesheets/{id}/approve
POST   /api/v1/timesheets/{id}/reject
"""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthUser, DbSession
from app.crud.timesheet import timesheet_crud
from app.models.timesheet import Timesheet
from app.schemas.timesheet import (
    TimesheetApprove,
    TimesheetCreate,
    TimesheetListResponse,
    TimesheetRead,
    TimesheetReject,
    TimesheetUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/timesheets", tags=["Timesheets"])


def _assert_tenant(ts: Timesheet, cu) -> None:
    """BOLA guard: ensure the timesheet belongs to the requesting tenant."""
    if ts.tenant_id != cu.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found.")


@router.get("", response_model=TimesheetListResponse, summary="List timesheets")
async def list_timesheets(
    cu: AuthUser,
    db: DbSession,
    employee_id: uuid.UUID | None = Query(None),
    project_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None, description="draft | submitted | approved | rejected"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TimesheetListResponse:
    items, total = await timesheet_crud.list(
        db, tenant_id=cu.tenant_id, employee_id=employee_id, project_id=project_id,
        status=status, page=page, page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total else 1
    return TimesheetListResponse(
        items=[TimesheetRead.model_validate(t) for t in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post("", response_model=TimesheetRead, status_code=status.HTTP_201_CREATED, summary="Create timesheet")
async def create_timesheet(
    payload: TimesheetCreate,
    cu: AuthUser,
    db: DbSession,
) -> TimesheetRead:
    ts = await timesheet_crud.create(db, payload, tenant_id=cu.tenant_id, created_by=cu.user_id)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="timesheets", entity_id=ts.id)
    return TimesheetRead.model_validate(ts)


@router.get("/{ts_id}", response_model=TimesheetRead, summary="Get timesheet by ID")
async def get_timesheet(
    ts_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> TimesheetRead:
    ts = await timesheet_crud.get(db, ts_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    _assert_tenant(ts, cu)
    return TimesheetRead.model_validate(ts)


@router.patch("/{ts_id}", response_model=TimesheetRead, summary="Update timesheet (draft only)")
async def update_timesheet(
    ts_id: uuid.UUID,
    payload: TimesheetUpdate,
    cu: AuthUser,
    db: DbSession,
) -> TimesheetRead:
    ts = await timesheet_crud.get(db, ts_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    _assert_tenant(ts, cu)
    if ts.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft timesheets can be edited.")
    updated = await timesheet_crud.update(db, ts, payload)
    return TimesheetRead.model_validate(updated)


@router.post("/{ts_id}/submit", response_model=TimesheetRead, summary="Submit timesheet for approval")
async def submit_timesheet(
    ts_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> TimesheetRead:
    ts = await timesheet_crud.get(db, ts_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    _assert_tenant(ts, cu)
    if ts.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft timesheets can be submitted.")
    if ts.total_hours <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot submit a timesheet with zero hours. Please enter daily hours first.",
        )
    updated = await timesheet_crud.submit(db, ts)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="submit", entity_type="timesheets", entity_id=ts.id)
    return TimesheetRead.model_validate(updated)


@router.post("/{ts_id}/approve", response_model=TimesheetRead, summary="Approve timesheet")
async def approve_timesheet(
    ts_id: uuid.UUID,
    payload: TimesheetApprove,
    cu: AuthUser,
    db: DbSession,
) -> TimesheetRead:
    cu.require_role("super_admin", "finance_hr", "projects")
    ts = await timesheet_crud.get(db, ts_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    _assert_tenant(ts, cu)
    if ts.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted timesheets can be approved.")
    if ts.total_hours <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot approve a timesheet with zero total hours.",
        )
    updated = await timesheet_crud.approve(db, ts, payload.approved_by)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="approve", entity_type="timesheets", entity_id=ts.id)
    return TimesheetRead.model_validate(updated)


@router.post("/{ts_id}/reject", response_model=TimesheetRead, summary="Reject timesheet")
async def reject_timesheet(
    ts_id: uuid.UUID,
    payload: TimesheetReject,
    cu: AuthUser,
    db: DbSession,
) -> TimesheetRead:
    cu.require_role("super_admin", "finance_hr", "projects")
    ts = await timesheet_crud.get(db, ts_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    _assert_tenant(ts, cu)
    if ts.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted timesheets can be rejected.")
    updated = await timesheet_crud.reject(db, ts, payload.rejection_reason)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="reject", entity_type="timesheets", entity_id=ts.id,
                    after_data={"rejection_reason": payload.rejection_reason})
    return TimesheetRead.model_validate(updated)
