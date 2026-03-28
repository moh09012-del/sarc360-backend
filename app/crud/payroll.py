"""
SARC360 ERP - Payroll CRUD with WPS export
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import PayrollRun
from app.schemas.payroll import PayrollCreate, PayrollUpdate


class PayrollCRUD:

    async def _next_number(self, db: AsyncSession, period_start: str) -> str:
        result = await db.execute(select(func.count()).select_from(PayrollRun))
        count: int = result.scalar_one()
        return f"PAY-{period_start}-{count + 1:03d}"

    async def create(
        self, db: AsyncSession, payload: PayrollCreate,
        created_by: uuid.UUID | None = None,
    ) -> PayrollRun:
        data = payload.model_dump()
        gross = (
            data["basic_salary_sar"]
            + data["housing_allowance_sar"]
            + data["transport_allowance_sar"]
            + data["other_allowances_sar"]
        )
        net = gross - data["gosi_employee_sar"] - data["other_deductions_sar"]

        period_str = str(data["pay_period_start"])[:7]  # e.g. 2026-03
        run = PayrollRun(
            **data,
            payroll_number=await self._next_number(db, period_str),
            gross_salary_sar=gross,
            net_salary_sar=net,
            created_by=created_by,
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)
        return run

    async def get(self, db: AsyncSession, run_id: uuid.UUID) -> PayrollRun | None:
        result = await db.execute(select(PayrollRun).where(PayrollRun.id == run_id))
        return result.scalar_one_or_none()

    async def list(
        self, db: AsyncSession, *,
        employee_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PayrollRun], int]:
        query = select(PayrollRun)
        if employee_id:
            query = query.where(PayrollRun.employee_id == employee_id)
        if status:
            query = query.where(PayrollRun.status == status)
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total: int = count_result.scalar_one()
        offset = (page - 1) * page_size
        query = query.order_by(PayrollRun.pay_period_start.desc()).offset(offset).limit(page_size)
        rows = await db.execute(query)
        return list(rows.scalars().all()), total

    async def update(
        self, db: AsyncSession, run: PayrollRun, payload: PayrollUpdate,
    ) -> PayrollRun:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(run, field, value)
        # Recompute gross and net
        run.gross_salary_sar = (
            run.basic_salary_sar + run.housing_allowance_sar
            + run.transport_allowance_sar + run.other_allowances_sar
        )
        run.net_salary_sar = run.gross_salary_sar - run.gosi_employee_sar - run.other_deductions_sar
        await db.flush()
        await db.refresh(run)
        return run

    async def approve(
        self, db: AsyncSession, run: PayrollRun, approved_by: uuid.UUID,
    ) -> PayrollRun:
        run.status = "approved"
        run.approved_by = approved_by
        run.approved_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(run)
        return run

    async def mark_paid(
        self, db: AsyncSession, run: PayrollRun,
        payment_date: str,
        bank_transfer_ref: str | None = None,
        wps_file_ref: str | None = None,
    ) -> PayrollRun:
        run.status = "paid"
        run.payment_date = payment_date
        run.bank_transfer_ref = bank_transfer_ref
        run.wps_file_ref = wps_file_ref
        await db.flush()
        await db.refresh(run)
        return run

    async def wps_export(
        self, db: AsyncSession, pay_period_start: str,
    ) -> list[dict]:
        """Generate WPS-compatible records for a pay period."""
        result = await db.execute(
            select(PayrollRun).where(
                PayrollRun.pay_period_start == pay_period_start,
                PayrollRun.status == "approved",
            )
        )
        runs = result.scalars().all()
        return [
            {
                "employee_id": str(r.employee_id),
                "payroll_number": r.payroll_number,
                "net_salary_sar": str(r.net_salary_sar),
                "pay_period_start": str(r.pay_period_start),
                "pay_period_end": str(r.pay_period_end),
            }
            for r in runs
        ]


payroll_crud = PayrollCRUD()
