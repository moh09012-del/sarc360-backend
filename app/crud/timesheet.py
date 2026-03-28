"""
SARC360 ERP - Timesheet CRUD
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timesheet import Timesheet
from app.schemas.timesheet import TimesheetCreate, TimesheetUpdate


class TimesheetCRUD:

    async def _next_number(self, db: AsyncSession) -> str:
        result = await db.execute(select(func.count()).select_from(Timesheet))
        count: int = result.scalar_one()
        return f"TS-{count + 1:04d}"

    async def create(
        self, db: AsyncSession, payload: TimesheetCreate,
        tenant_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Timesheet:
        ts = Timesheet(
            **payload.model_dump(),
            timesheet_number=await self._next_number(db),
            created_by=created_by,
        )
        if tenant_id and not ts.tenant_id:
            ts.tenant_id = tenant_id
        db.add(ts)
        await db.flush()
        await db.refresh(ts)
        return ts

    async def get(self, db: AsyncSession, ts_id: uuid.UUID) -> Timesheet | None:
        result = await db.execute(select(Timesheet).where(Timesheet.id == ts_id))
        return result.scalar_one_or_none()

    async def list(
        self, db: AsyncSession, *,
        tenant_id: uuid.UUID | None = None,
        employee_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Timesheet], int]:
        query = select(Timesheet)
        if tenant_id:
            query = query.where(Timesheet.tenant_id == tenant_id)
        if employee_id:
            query = query.where(Timesheet.employee_id == employee_id)
        if project_id:
            query = query.where(Timesheet.project_id == project_id)
        if status:
            query = query.where(Timesheet.status == status)
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total: int = count_result.scalar_one()
        offset = (page - 1) * page_size
        query = query.order_by(Timesheet.week_start_date.desc()).offset(offset).limit(page_size)
        rows = await db.execute(query)
        return list(rows.scalars().all()), total

    async def update(
        self, db: AsyncSession, ts: Timesheet, payload: TimesheetUpdate,
    ) -> Timesheet:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(ts, field, value)
        await db.flush()
        await db.refresh(ts)
        return ts

    async def submit(self, db: AsyncSession, ts: Timesheet) -> Timesheet:
        ts.status = "submitted"
        ts.submitted_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(ts)
        return ts

    async def approve(
        self, db: AsyncSession, ts: Timesheet, approved_by: uuid.UUID,
    ) -> Timesheet:
        ts.status = "approved"
        ts.approved_at = datetime.now(timezone.utc)
        ts.approved_by = approved_by
        await db.flush()
        await db.refresh(ts)
        return ts

    async def reject(
        self, db: AsyncSession, ts: Timesheet, reason: str,
    ) -> Timesheet:
        ts.status = "rejected"
        ts.rejection_reason = reason
        await db.flush()
        await db.refresh(ts)
        return ts


timesheet_crud = TimesheetCRUD()
