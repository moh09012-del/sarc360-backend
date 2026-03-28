"""
SARC360 ERP - Employees Router
GET    /api/v1/employees
POST   /api/v1/employees
GET    /api/v1/employees/{id}
PATCH  /api/v1/employees/{id}
DELETE /api/v1/employees/{id}      (soft — sets status=terminated)
GET    /api/v1/employees/alerts/expiring-documents
"""

import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.employee import employee_crud
from app.models.employee import Employee
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeRead,
    EmployeeUpdate,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


# ── GET /employees ─────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=EmployeeListResponse,
    summary="List employees",
    description="Returns a paginated list of employees with optional filters.",
)
async def list_employees(
    status: str | None = Query(None, description="active | on_leave | terminated"),
    department: str | None = Query(None),
    nationality: str | None = Query(None),
    search: str | None = Query(None, description="Search by name, employee #, or iqama"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> EmployeeListResponse:
    employees, total = await employee_crud.list(
        db,
        status=status,
        department=department,
        nationality=nationality,
        search=search,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total else 1
    return EmployeeListResponse(
        items=[EmployeeRead.model_validate(e) for e in employees],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ── POST /employees ────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create employee",
)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    # Duplicate Iqama check
    if payload.iqama_number:
        existing = await employee_crud.get_by_iqama(db, payload.iqama_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with Iqama {payload.iqama_number} already exists.",
            )
    employee = await employee_crud.create(db, payload)
    return EmployeeRead.model_validate(employee)


# ── GET /employees/{id} ────────────────────────────────────────────────────────
@router.get(
    "/{employee_id}",
    response_model=EmployeeRead,
    summary="Get employee by ID",
)
async def get_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    employee = await employee_crud.get(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found.",
        )
    return EmployeeRead.model_validate(employee)


# ── PATCH /employees/{id} ──────────────────────────────────────────────────────
@router.patch(
    "/{employee_id}",
    response_model=EmployeeRead,
    summary="Update employee",
)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    employee = await employee_crud.get(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    # Duplicate Iqama check if changing iqama
    if payload.iqama_number and payload.iqama_number != employee.iqama_number:
        existing = await employee_crud.get_by_iqama(db, payload.iqama_number)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Iqama {payload.iqama_number} already assigned to another employee.",
            )

    updated = await employee_crud.update(db, employee, payload)
    return EmployeeRead.model_validate(updated)


# ── DELETE /employees/{id} (soft) ─────────────────────────────────────────────
@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate employee (soft delete)",
)
async def terminate_employee(
    employee_id: uuid.UUID,
    termination_date: date = Query(default=None),
    reason: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    employee = await employee_crud.get(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if employee.status == "terminated":
        raise HTTPException(status_code=409, detail="Employee is already terminated.")

    t_date = termination_date or date.today()
    await employee_crud.terminate(db, employee, t_date, reason)


# ── GET /employees/alerts/expiring-documents ──────────────────────────────────
@router.get(
    "/alerts/expiring-documents",
    response_model=list[EmployeeRead],
    summary="Employees with Iqama expiring soon",
    description="Returns active employees whose Iqama expires within `days` days (default 60).",
)
async def expiring_documents_alert(
    days: int = Query(60, ge=1, le=365, description="Look-ahead window in days"),
    db: AsyncSession = Depends(get_db),
) -> list[EmployeeRead]:
    employees = await employee_crud.list_expiring_iqama(db, within_days=days)
    return [EmployeeRead.model_validate(e) for e in employees]
