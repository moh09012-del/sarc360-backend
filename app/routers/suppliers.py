"""
SARC360 ERP - Suppliers Router
GET    /api/v1/suppliers
POST   /api/v1/suppliers
GET    /api/v1/suppliers/{id}
PATCH  /api/v1/suppliers/{id}
DELETE /api/v1/suppliers/{id}   (soft)
"""
import math
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import AuthUser, DbSession
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierListResponse, SupplierRead, SupplierUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


async def _get_or_404(db: DbSession, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
    res = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    return obj


@router.get("", response_model=SupplierListResponse, summary="List suppliers")
async def list_suppliers(
    cu: AuthUser,
    db: DbSession,
    supplier_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SupplierListResponse:
    q = select(Supplier).where(Supplier.tenant_id == cu.tenant_id)
    if supplier_type:
        q = q.where(Supplier.supplier_type == supplier_type)
    if is_active is not None:
        q = q.where(Supplier.is_active == is_active)
    if search:
        q = q.where(Supplier.name.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.order_by(Supplier.name).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return SupplierListResponse(
        items=[SupplierRead.model_validate(s) for s in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED, summary="Create supplier")
async def create_supplier(payload: SupplierCreate, cu: AuthUser, db: DbSession) -> SupplierRead:
    cu.require_role("super_admin", "finance_hr")

    dup = await db.execute(
        select(Supplier).where(Supplier.tenant_id == cu.tenant_id, Supplier.name == payload.name)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier name already exists.")

    obj = Supplier(tenant_id=cu.tenant_id, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="suppliers", entity_id=obj.id,
                    after_data=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(obj)
    return SupplierRead.model_validate(obj)


@router.get("/{supplier_id}", response_model=SupplierRead, summary="Get supplier")
async def get_supplier(supplier_id: uuid.UUID, cu: AuthUser, db: DbSession) -> SupplierRead:
    return SupplierRead.model_validate(await _get_or_404(db, cu.tenant_id, supplier_id))


@router.patch("/{supplier_id}", response_model=SupplierRead, summary="Update supplier")
async def update_supplier(
    supplier_id: uuid.UUID, payload: SupplierUpdate, cu: AuthUser, db: DbSession
) -> SupplierRead:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, supplier_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="update", entity_type="suppliers", entity_id=obj.id,
                    after_data=payload.model_dump(mode="json", exclude_none=True))
    await db.commit()
    await db.refresh(obj)
    return SupplierRead.model_validate(obj)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate supplier (soft delete)")
async def deactivate_supplier(supplier_id: uuid.UUID, cu: AuthUser, db: DbSession) -> None:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, supplier_id)
    if not obj.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier already inactive.")
    obj.is_active = False
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="delete", entity_type="suppliers", entity_id=obj.id)
    await db.commit()
