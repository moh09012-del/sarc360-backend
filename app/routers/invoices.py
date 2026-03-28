"""
SARC360 ERP - Invoices Router
GET    /api/v1/invoices
POST   /api/v1/invoices
GET    /api/v1/invoices/{id}
PATCH  /api/v1/invoices/{id}
POST   /api/v1/invoices/{id}/gl-post
POST   /api/v1/invoices/{id}/mark-paid
"""

import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthUser, DbSession
from app.crud.invoice import invoice_crud
from app.models.invoice import Invoice
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceRead,
    InvoiceUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _assert_tenant(invoice: Invoice, cu) -> None:
    """BOLA guard: ensure the invoice belongs to the requesting tenant."""
    if invoice.tenant_id != cu.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")


@router.get("", response_model=InvoiceListResponse, summary="List invoices")
async def list_invoices(
    cu: AuthUser,
    db: DbSession,
    status: str | None = Query(None, description="draft | sent | paid | overdue | cancelled"),
    project_id: uuid.UUID | None = Query(None),
    zatca_status: str | None = Query(None, description="pending | submitted | approved | rejected"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    items, total = await invoice_crud.list(
        db, tenant_id=cu.tenant_id, status=status, project_id=project_id,
        zatca_status=zatca_status, page=page, page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total else 1
    return InvoiceListResponse(
        items=[InvoiceRead.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED, summary="Create invoice")
async def create_invoice(
    payload: InvoiceCreate,
    cu: AuthUser,
    db: DbSession,
) -> InvoiceRead:
    # Inject tenant_id from JWT — never trust client
    invoice = await invoice_crud.create(db, payload, tenant_id=cu.tenant_id, created_by=cu.user_id)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="invoices", entity_id=invoice.id)
    return InvoiceRead.model_validate(invoice)


@router.get("/{invoice_id}", response_model=InvoiceRead, summary="Get invoice by ID")
async def get_invoice(
    invoice_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> InvoiceRead:
    invoice = await invoice_crud.get(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    _assert_tenant(invoice, cu)
    return InvoiceRead.model_validate(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceRead, summary="Update invoice")
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    cu: AuthUser,
    db: DbSession,
) -> InvoiceRead:
    invoice = await invoice_crud.get(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    _assert_tenant(invoice, cu)
    if invoice.status == "paid":
        raise HTTPException(status_code=409, detail="Paid invoices cannot be edited.")
    updated = await invoice_crud.update(db, invoice, payload, updated_by=cu.user_id)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="update", entity_type="invoices", entity_id=invoice.id,
                    after_data=payload.model_dump(exclude_unset=True))
    return InvoiceRead.model_validate(updated)


@router.post("/{invoice_id}/gl-post", response_model=InvoiceRead, summary="Post invoice to GL")
async def gl_post_invoice(
    invoice_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> InvoiceRead:
    cu.require_role("super_admin", "finance_hr")
    invoice = await invoice_crud.get(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    _assert_tenant(invoice, cu)
    if invoice.gl_posted:
        raise HTTPException(status_code=409, detail="Invoice already posted to GL.")

    if invoice.po_id:
        from app.models.contract import Contract

        contract_res = await db.execute(
            select(Contract)
            .where(Contract.id == invoice.po_id, Contract.tenant_id == cu.tenant_id)
            .with_for_update()
        )
        contract = contract_res.scalar_one_or_none()
        if not contract:
            raise HTTPException(status_code=404, detail="Related contract not found.")

        inv_sum_res = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_sar), 0)).where(
                Invoice.tenant_id == cu.tenant_id,
                Invoice.po_id == contract.id,
                Invoice.status.in_(["posted", "paid"]),
            )
        )
        invoiced = inv_sum_res.scalar_one() or 0
        remaining = contract.total_value - invoiced
        if invoice.total_sar > remaining:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invoice amount {invoice.total_sar} SAR exceeds remaining "
                    f"contract value {remaining} SAR. Over-invoicing is not allowed."
                ),
            )

    updated = await invoice_crud.gl_post(db, invoice)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="gl_post", entity_type="invoices", entity_id=invoice.id)
    return InvoiceRead.model_validate(updated)


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceRead, summary="Mark invoice as paid")
async def mark_invoice_paid(
    invoice_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
    payment_date: date = Query(...),
    payment_reference: str | None = Query(None),
) -> InvoiceRead:
    cu.require_role("super_admin", "finance_hr")
    invoice = await invoice_crud.get(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    _assert_tenant(invoice, cu)
    if invoice.status == "paid":
        raise HTTPException(status_code=409, detail="Invoice is already paid.")
    updated = await invoice_crud.mark_paid(db, invoice, payment_date, payment_reference)
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="mark_paid", entity_type="invoices", entity_id=invoice.id,
                    after_data={"payment_date": str(payment_date), "payment_reference": payment_reference})
    return InvoiceRead.model_validate(updated)
