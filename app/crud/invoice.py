"""
SARC360 ERP - Invoice CRUD with GL auto-post
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


class InvoiceCRUD:

    async def _next_number(self, db: AsyncSession) -> str:
        result = await db.execute(select(func.count()).select_from(Invoice))
        count: int = result.scalar_one()
        year = datetime.now().year
        return f"INV-{year}-{count + 1:04d}"

    async def create(
        self, db: AsyncSession, payload: InvoiceCreate,
        tenant_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Invoice:
        data = payload.model_dump()
        # Compute VAT and total
        subtotal = data["subtotal_sar"]
        vat_rate = data["vat_rate"]
        vat_amount = (subtotal * vat_rate).quantize(Decimal("0.01"))
        total = subtotal + vat_amount

        invoice = Invoice(
            **data,
            invoice_number=await self._next_number(db),
            vat_amount_sar=vat_amount,
            total_sar=total,
            created_by=created_by,
        )
        if tenant_id and not invoice.tenant_id:
            invoice.tenant_id = tenant_id
        db.add(invoice)
        await db.flush()
        await db.refresh(invoice)
        return invoice

    async def get(self, db: AsyncSession, invoice_id: uuid.UUID) -> Invoice | None:
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        return result.scalar_one_or_none()

    async def list(
        self, db: AsyncSession, *,
        tenant_id: uuid.UUID | None = None,
        status: str | None = None,
        project_id: uuid.UUID | None = None,
        zatca_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Invoice], int]:
        query = select(Invoice)
        if tenant_id:
            query = query.where(Invoice.tenant_id == tenant_id)
        if status:
            query = query.where(Invoice.status == status)
        if project_id:
            query = query.where(Invoice.project_id == project_id)
        if zatca_status:
            query = query.where(Invoice.zatca_status == zatca_status)
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total: int = count_result.scalar_one()
        offset = (page - 1) * page_size
        query = query.order_by(Invoice.invoice_date.desc()).offset(offset).limit(page_size)
        rows = await db.execute(query)
        return list(rows.scalars().all()), total

    async def update(
        self, db: AsyncSession, invoice: Invoice, payload: InvoiceUpdate,
        updated_by: uuid.UUID | None = None,
    ) -> Invoice:
        data = payload.model_dump(exclude_unset=True)
        # Recompute totals if subtotal changed
        if "subtotal_sar" in data:
            vat_rate = invoice.vat_rate
            vat_amount = (data["subtotal_sar"] * vat_rate).quantize(Decimal("0.01"))
            data["vat_amount_sar"] = vat_amount
            data["total_sar"] = data["subtotal_sar"] + vat_amount
        for field, value in data.items():
            setattr(invoice, field, value)
        if updated_by:
            invoice.updated_by = updated_by
        await db.flush()
        await db.refresh(invoice)
        return invoice

    async def gl_post(self, db: AsyncSession, invoice: Invoice) -> Invoice:
        """Auto-post invoice to GL."""
        invoice.gl_posted = True
        invoice.gl_posted_at = datetime.now(timezone.utc)
        invoice.gl_entry_ref = f"GL-{invoice.invoice_number}"
        await db.flush()
        await db.refresh(invoice)
        return invoice

    async def mark_paid(
        self, db: AsyncSession, invoice: Invoice,
        payment_date: str, payment_reference: str | None = None,
    ) -> Invoice:
        invoice.status = "paid"
        invoice.payment_date = payment_date
        invoice.payment_reference = payment_reference
        await db.flush()
        await db.refresh(invoice)
        return invoice


invoice_crud = InvoiceCRUD()
