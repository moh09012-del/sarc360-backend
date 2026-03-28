"""
SARC360 ERP - Contracts / PO Router
GET    /api/v1/contracts
POST   /api/v1/contracts
GET    /api/v1/contracts/{id}
PATCH  /api/v1/contracts/{id}
POST   /api/v1/contracts/{id}/gl-post   (validates PO remaining value)
"""
import math
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import AuthUser, DbSession
from app.models.contract import Contract
from app.models.invoice import Invoice
from app.schemas.contract import (
    ContractCreate,
    ContractListResponse,
    ContractRead,
    ContractUpdate,
    ContractUtilizationResponse,
)
from app.services.audit import log_event

router = APIRouter(prefix="/contracts", tags=["Contracts / PO"])


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: DbSession, tenant_id: uuid.UUID, contract_id: uuid.UUID) -> Contract:
    res = await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    return obj


async def _remaining_value(db: DbSession, tenant_id: uuid.UUID, contract_id: uuid.UUID, total_value: Decimal) -> Decimal:
    """Sum of invoiced amounts on this PO (posted or paid)."""
    res = await db.execute(
        select(func.coalesce(func.sum(Invoice.total_sar), Decimal("0.00"))).where(
            Invoice.tenant_id == tenant_id,
            Invoice.po_id == contract_id,
            Invoice.status.in_(["posted", "paid"]),
        )
    )
    invoiced = res.scalar_one()
    return total_value - invoiced


def _read(obj: Contract, remaining: Decimal) -> ContractRead:
    data = ContractRead.model_validate(obj)
    data.remaining_value = remaining
    return data


# ── GET /contracts ────────────────────────────────────────────────────────────

@router.get("", response_model=ContractListResponse, summary="List contracts")
async def list_contracts(
    cu: AuthUser,
    db: DbSession,
    client_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ContractListResponse:
    q = select(Contract).where(Contract.tenant_id == cu.tenant_id)
    if client_id:
        q = q.where(Contract.client_id == client_id)
    if status_filter:
        q = q.where(Contract.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.order_by(Contract.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()

    items = []
    for c in rows:
        rem = await _remaining_value(db, cu.tenant_id, c.id, c.total_value)
        items.append(_read(c, rem))

    return ContractListResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


# ── POST /contracts ───────────────────────────────────────────────────────────

@router.post("", response_model=ContractRead, status_code=status.HTTP_201_CREATED, summary="Create contract / PO")
async def create_contract(
    payload: ContractCreate,
    cu: AuthUser,
    db: DbSession,
) -> ContractRead:
    cu.require_role("super_admin", "finance_hr")

    dup = await db.execute(
        select(Contract).where(
            Contract.tenant_id == cu.tenant_id,
            Contract.client_id == payload.client_id,
            Contract.po_number == payload.po_number,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PO number already exists for this client.")

    obj = Contract(tenant_id=cu.tenant_id, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await log_event(
        db,
        tenant_id=cu.tenant_id,
        actor_user_id=cu.user_id,
        action="create",
        entity_type="contracts",
        entity_id=obj.id,
        after_data=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(obj)
    rem = await _remaining_value(db, cu.tenant_id, obj.id, obj.total_value)
    return _read(obj, rem)


# ── GET /contracts/{id} ───────────────────────────────────────────────────────

@router.get("/{contract_id}", response_model=ContractRead, summary="Get contract")
async def get_contract(contract_id: uuid.UUID, cu: AuthUser, db: DbSession) -> ContractRead:
    obj = await _get_or_404(db, cu.tenant_id, contract_id)
    rem = await _remaining_value(db, cu.tenant_id, obj.id, obj.total_value)
    return _read(obj, rem)

@router.get("/{contract_id}/utilization", response_model=ContractUtilizationResponse,
            summary="Get contract utilization (invoiced/remaining)")
async def get_contract_utilization(contract_id: uuid.UUID, cu: AuthUser, db: DbSession) -> ContractUtilizationResponse:
    obj = await _get_or_404(db, cu.tenant_id, contract_id)
    inv_res = await db.execute(
        select(func.coalesce(func.sum(Invoice.total_sar), Decimal("0.00"))).where(
            Invoice.tenant_id == cu.tenant_id,
            Invoice.po_id == obj.id,
            Invoice.status.in_(["posted", "paid"]),
        )
    )
    invoiced = inv_res.scalar_one()
    remaining = obj.total_value - invoiced
    percentage = Decimal("0.00")
    if obj.total_value and obj.total_value > 0:
        percentage = (invoiced / obj.total_value * 100).quantize(Decimal("0.01"))

    return ContractUtilizationResponse(
        id=obj.id,
        total_value=obj.total_value,
        invoiced=invoiced,
        remaining=remaining,
        percentage_used=percentage,
    )

# ── PATCH /contracts/{id} ─────────────────────────────────────────────────────

@router.patch("/{contract_id}", response_model=ContractRead, summary="Update contract")
async def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    cu: AuthUser,
    db: DbSession,
) -> ContractRead:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, contract_id)
    before = {c.key: str(getattr(obj, c.key)) for c in obj.__table__.columns}

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)

    await db.flush()
    await log_event(
        db,
        tenant_id=cu.tenant_id,
        actor_user_id=cu.user_id,
        action="update",
        entity_type="contracts",
        entity_id=obj.id,
        before_data=before,
        after_data=payload.model_dump(mode="json", exclude_none=True),
    )
    await db.commit()
    await db.refresh(obj)
    rem = await _remaining_value(db, cu.tenant_id, obj.id, obj.total_value)
    return _read(obj, rem)


# ── POST /contracts/{id}/gl-post ─────────────────────────────────────────────

@router.post("/{contract_id}/gl-post", response_model=ContractRead, summary="GL-post: enforce PO value limit")
async def gl_post_contract(
    contract_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
    invoice_amount: Decimal = Query(..., gt=0, description="Amount to post against this PO"),
) -> ContractRead:
    """
    Validate that posting `invoice_amount` won't exceed the PO remaining value.
    Uses SELECT FOR UPDATE to prevent concurrent over-posting.
    """
    cu.require_role("super_admin", "finance_hr")

    # Lock the contract row
    res = await db.execute(
        select(Contract)
        .where(Contract.id == contract_id, Contract.tenant_id == cu.tenant_id)
        .with_for_update()
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    if obj.status not in ("active", "draft"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Contract is {obj.status}.")

    rem = await _remaining_value(db, cu.tenant_id, obj.id, obj.total_value)
    if invoice_amount > rem:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invoice amount {invoice_amount} exceeds PO remaining value {rem}.",
        )

    await log_event(
        db,
        tenant_id=cu.tenant_id,
        actor_user_id=cu.user_id,
        action="post",
        entity_type="contracts",
        entity_id=obj.id,
        after_data={"invoice_amount": str(invoice_amount), "remaining_before": str(rem)},
    )
    await db.commit()
    rem_after = rem - invoice_amount
    return _read(obj, rem_after)
