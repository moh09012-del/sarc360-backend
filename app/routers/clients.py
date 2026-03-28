"""
SARC360 ERP - Clients Router
GET    /api/v1/clients
POST   /api/v1/clients
GET    /api/v1/clients/{id}
PATCH  /api/v1/clients/{id}
DELETE /api/v1/clients/{id}   (soft — sets is_active=False)
"""
import math
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import AuthUser, DbSession
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientListResponse, ClientRead, ClientUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/clients", tags=["Clients"])


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: DbSession, tenant_id: uuid.UUID, client_id: uuid.UUID) -> Client:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.tenant_id == tenant_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return obj


# ── GET /clients ───────────────────────────────────────────────────────────────

@router.get("", response_model=ClientListResponse, summary="List clients")
async def list_clients(
    cu: AuthUser,
    db: DbSession,
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ClientListResponse:
    q = select(Client).where(Client.tenant_id == cu.tenant_id)
    if is_active is not None:
        q = q.where(Client.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        q = q.where(Client.name_en.ilike(pattern) | Client.name_ar.ilike(pattern))

    total_res = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_res.scalar_one()

    items_res = await db.execute(
        q.order_by(Client.name_en).offset((page - 1) * page_size).limit(page_size)
    )
    items = items_res.scalars().all()
    pages = math.ceil(total / page_size) if total else 1
    return ClientListResponse(
        items=[ClientRead.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ── POST /clients ──────────────────────────────────────────────────────────────

@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED, summary="Create client")
async def create_client(
    payload: ClientCreate,
    cu: AuthUser,
    db: DbSession,
) -> ClientRead:
    cu.require_role("super_admin", "finance_hr")

    # duplicate name check
    dup = await db.execute(
        select(Client).where(
            Client.tenant_id == cu.tenant_id,
            Client.name_en == payload.name_en,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Client name already exists.")

    obj = Client(tenant_id=cu.tenant_id, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await log_event(
        db,
        tenant_id=cu.tenant_id,
        actor_user_id=cu.user_id,
        action="create",
        entity_type="clients",
        entity_id=obj.id,
        after_data=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(obj)
    return ClientRead.model_validate(obj)


# ── GET /clients/{id} ─────────────────────────────────────────────────────────

@router.get("/{client_id}", response_model=ClientRead, summary="Get client")
async def get_client(client_id: uuid.UUID, cu: AuthUser, db: DbSession) -> ClientRead:
    obj = await _get_or_404(db, cu.tenant_id, client_id)
    return ClientRead.model_validate(obj)


# ── PATCH /clients/{id} ───────────────────────────────────────────────────────

@router.patch("/{client_id}", response_model=ClientRead, summary="Update client")
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    cu: AuthUser,
    db: DbSession,
) -> ClientRead:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, client_id)
    before = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)

    await db.flush()
    await log_event(
        db,
        tenant_id=cu.tenant_id,
        actor_user_id=cu.user_id,
        action="update",
        entity_type="clients",
        entity_id=obj.id,
        before_data={k: str(v) for k, v in before.items()},
        after_data=payload.model_dump(mode="json", exclude_none=True),
    )
    await db.commit()
    await db.refresh(obj)
    return ClientRead.model_validate(obj)


# ── DELETE /clients/{id} ──────────────────────────────────────────────────────

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate client (soft delete)")
async def deactivate_client(
    client_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> None:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, client_id)
    if not obj.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Client already inactive.")
    obj.is_active = False
    await db.flush()
    await log_event(
        db,
        tenant_id=cu.tenant_id,
        actor_user_id=cu.user_id,
        action="delete",
        entity_type="clients",
        entity_id=obj.id,
    )
    await db.commit()
