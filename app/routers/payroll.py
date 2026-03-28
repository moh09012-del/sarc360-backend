"""
SARC360 ERP - Payroll Router
GET    /api/v1/payroll
POST   /api/v1/payroll
GET    /api/v1/payroll/{id}
PATCH  /api/v1/payroll/{id}
POST   /api/v1/payroll/{id}/approve
POST   /api/v1/payroll/{id}/mark-paid
GET    /api/v1/payroll/wps-export
"""

import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.payroll import payroll_crud
from app.schemas.payroll import (
    PayrollApprove,
    PayrollCreate,
    PayrollListResponse,
    PayrollMarkPaid,
    PayrollRead,
    PayrollUpdate,
)

router = APIRouter(prefix="/payroll", tags=["Payroll"])


@router.get("", response_model=PayrollListResponse, summary="List payroll runs")
async def list_payroll(
    employee_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None, description="draft | approved | paid"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PayrollListResponse:
    items, total = await payroll_crud.list(
        db, employee_id=employee_id, status=status,
        page=page, page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total else 1
    return PayrollListResponse(
        items=[PayrollRead.model_validate(r) for r in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post("", response_model=PayrollRead, status_code=status.HTTP_201_CREATED, summary="Create payroll run")
async def create_payroll(
    payload: PayrollCreate,
    db: AsyncSession = Depends(get_db),
) -> PayrollRead:
    run = await payroll_crud.create(db, payload)
    return PayrollRead.model_validate(run)


@router.get("/wps-export", summary="Export approved payroll as WPS file")
async def wps_export(
    pay_period_start: date = Query(..., description="Start date of pay period e.g. 2026-03-01"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await payroll_crud.wps_export(db, str(pay_period_start))


@router.get("/{run_id}", response_model=PayrollRead, summary="Get payroll run by ID")
async def get_payroll(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PayrollRead:
    run = await payroll_crud.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found.")
    return PayrollRead.model_validate(run)


@router.patch("/{run_id}", response_model=PayrollRead, summary="Update payroll run (draft only)")
async def update_payroll(
    run_id: uuid.UUID,
    payload: PayrollUpdate,
    db: AsyncSession = Depends(get_db),
) -> PayrollRead:
    run = await payroll_crud.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found.")
    if run.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft payroll runs can be edited.")
    updated = await payroll_crud.update(db, run, payload)
    return PayrollRead.model_validate(updated)


@router.post("/{run_id}/approve", response_model=PayrollRead, summary="Approve payroll run")
async def approve_payroll(
    run_id: uuid.UUID,
    payload: PayrollApprove,
    db: AsyncSession = Depends(get_db),
) -> PayrollRead:
    run = await payroll_crud.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found.")
    if run.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft payroll runs can be approved.")
    updated = await payroll_crud.approve(db, run, payload.approved_by)
    return PayrollRead.model_validate(updated)


@router.post("/{run_id}/mark-paid", response_model=PayrollRead, summary="Mark payroll as paid (WPS)")
async def mark_payroll_paid(
    run_id: uuid.UUID,
    payload: PayrollMarkPaid,
    db: AsyncSession = Depends(get_db),
) -> PayrollRead:
    run = await payroll_crud.get(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found.")
    if run.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved payroll runs can be marked as paid.")
    updated = await payroll_crud.mark_paid(
        db, run, payload.payment_date, payload.bank_transfer_ref, payload.wps_file_ref
    )
    return PayrollRead.model_validate(updated)
