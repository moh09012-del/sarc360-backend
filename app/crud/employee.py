"""
SARC360 ERP - Employee CRUD (async SQLAlchemy)
"""
from __future__ import annotations

import math
import uuid
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


class EmployeeCRUD:

    # ── Helpers ───────────────────────────────────────────────────────────────
    async def _next_employee_number(self, db: AsyncSession) -> str:
        """Auto-generate EMP-001, EMP-002, ..."""
        result = await db.execute(
            select(func.count()).select_from(Employee)
        )
        count: int = result.scalar_one()
        return f"EMP-{count + 1:03d}"

    # ── Create ────────────────────────────────────────────────────────────────
    async def create(
        self,
        db: AsyncSession,
        payload: EmployeeCreate,
        created_by: uuid.UUID | None = None,
    ) -> Employee:
        emp = Employee(
            **payload.model_dump(),
            employee_number=await self._next_employee_number(db),
            created_by=created_by,
        )
        db.add(emp)
        await db.flush()          # Get the generated ID before commit
        await db.refresh(emp)
        return emp

    # ── Read one ──────────────────────────────────────────────────────────────
    async def get(self, db: AsyncSession, employee_id: uuid.UUID) -> Employee | None:
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        return result.scalar_one_or_none()

    async def get_by_iqama(
        self, db: AsyncSession, iqama_number: str
    ) -> Employee | None:
        result = await db.execute(
            select(Employee).where(Employee.iqama_number == iqama_number)
        )
        return result.scalar_one_or_none()

    # ── List with filters + pagination ────────────────────────────────────────
    async def list(
        self,
        db: AsyncSession,
        *,
        status: str | None = None,
        department: str | None = None,
        nationality: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Employee], int]:
        query = select(Employee)

        if status:
            query = query.where(Employee.status == status)
        if department:
            query = query.where(Employee.department == department)
        if nationality:
            query = query.where(Employee.nationality == nationality)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Employee.full_name_en.ilike(pattern),
                    Employee.full_name_ar.ilike(pattern),
                    Employee.employee_number.ilike(pattern),
                    Employee.iqama_number.ilike(pattern),
                )
            )

        # Total count
        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total: int = count_result.scalar_one()

        # Paginated rows
        offset = (page - 1) * page_size
        query = query.order_by(Employee.employee_number).offset(offset).limit(page_size)
        rows = await db.execute(query)
        employees = list(rows.scalars().all())

        return employees, total

    # ── Update ────────────────────────────────────────────────────────────────
    async def update(
        self,
        db: AsyncSession,
        employee: Employee,
        payload: EmployeeUpdate,
        updated_by: uuid.UUID | None = None,
    ) -> Employee:
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(employee, field, value)
        if updated_by:
            employee.updated_by = updated_by
        await db.flush()
        await db.refresh(employee)
        return employee

    # ── Soft delete (status = terminated) ────────────────────────────────────
    async def terminate(
        self,
        db: AsyncSession,
        employee: Employee,
        termination_date: date,
        reason: str | None = None,
    ) -> Employee:
        employee.status = "terminated"
        employee.termination_date = termination_date
        employee.termination_reason = reason
        await db.flush()
        await db.refresh(employee)
        return employee

    # ── Expiring documents alert query ────────────────────────────────────────
    async def list_expiring_iqama(
        self,
        db: AsyncSession,
        within_days: int = 60,
    ) -> list[Employee]:
        today = date.today()
        threshold = today + timedelta(days=within_days)
        result = await db.execute(
            select(Employee)
            .where(
                Employee.status == "active",
                Employee.iqama_expiry_date.isnot(None),
                Employee.iqama_expiry_date <= threshold,
            )
            .order_by(Employee.iqama_expiry_date)
        )
        return list(result.scalars().all())


employee_crud = EmployeeCRUD()
