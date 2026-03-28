"""
SARC360 ERP - Expenses Router
GET    /api/v1/expenses
POST   /api/v1/expenses
GET    /api/v1/expenses/{id}
PATCH  /api/v1/expenses/{id}
POST   /api/v1/expenses/{id}/gl-post   (GL posting with FOR UPDATE)
DELETE /api/v1/expenses/{id}           (void — soft)
"""
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import AuthUser, DbSession
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseListResponse, ExpenseRead, ExpenseUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/expenses", tags=["Expenses"])


async def _get_or_404(db: DbSession, tenant_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    res = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.tenant_id == tenant_id)
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
    return obj


@router.get("", response_model=ExpenseListResponse, summary="List expenses")
async def list_expenses(
    cu: AuthUser,
    db: DbSession,
    project_id: uuid.UUID | None = Query(None),
    supplier_id: uuid.UUID | None = Query(None),
    category: str | None = Query(None),
    expense_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ExpenseListResponse:
    q = select(Expense).where(Expense.tenant_id == cu.tenant_id)
    if project_id:
        q = q.where(Expense.project_id == project_id)
    if supplier_id:
        q = q.where(Expense.supplier_id == supplier_id)
    if category:
        q = q.where(Expense.category == category)
    if expense_status:
        q = q.where(Expense.status == expense_status)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(
        q.order_by(Expense.expense_date.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return ExpenseListResponse(
        items=[ExpenseRead.model_validate(e) for e in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED, summary="Create expense")
async def create_expense(payload: ExpenseCreate, cu: AuthUser, db: DbSession) -> ExpenseRead:
    cu.require_role("super_admin", "finance_hr", "projects")

    amount_gross = payload.amount_net + payload.vat_amount
    obj = Expense(
        tenant_id=cu.tenant_id,
        created_by=cu.user_id,
        amount_gross=amount_gross,
        **payload.model_dump(),
    )
    db.add(obj)
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="create", entity_type="expenses", entity_id=obj.id,
                    after_data=payload.model_dump(mode="json"))
    await db.commit()
    await db.refresh(obj)
    return ExpenseRead.model_validate(obj)


@router.get("/{expense_id}", response_model=ExpenseRead, summary="Get expense")
async def get_expense(expense_id: uuid.UUID, cu: AuthUser, db: DbSession) -> ExpenseRead:
    return ExpenseRead.model_validate(await _get_or_404(db, cu.tenant_id, expense_id))


@router.patch("/{expense_id}", response_model=ExpenseRead, summary="Update expense")
async def update_expense(
    expense_id: uuid.UUID, payload: ExpenseUpdate, cu: AuthUser, db: DbSession
) -> ExpenseRead:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, expense_id)
    if obj.status == "posted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a posted expense.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)

    # Recompute gross if net or vat changed
    obj.amount_gross = obj.amount_net + obj.vat_amount

    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="update", entity_type="expenses", entity_id=obj.id,
                    after_data=payload.model_dump(mode="json", exclude_none=True))
    await db.commit()
    await db.refresh(obj)
    return ExpenseRead.model_validate(obj)


@router.post("/{expense_id}/gl-post", response_model=ExpenseRead, summary="GL-post expense")
async def gl_post_expense(expense_id: uuid.UUID, cu: AuthUser, db: DbSession) -> ExpenseRead:
    """Post expense to GL. Uses SELECT FOR UPDATE to prevent double-posting."""
    cu.require_role("super_admin", "finance_hr")

    res = await db.execute(
        select(Expense)
        .where(Expense.id == expense_id, Expense.tenant_id == cu.tenant_id)
        .with_for_update()
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
    if obj.status == "posted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Expense already posted.")
    if obj.status == "void":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot post a void expense.")

    obj.status = "posted"
    obj.gl_posted_at = datetime.now(tz=timezone.utc)

    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="post", entity_type="expenses", entity_id=obj.id,
                    after_data={"gl_posted_at": obj.gl_posted_at.isoformat()})
    await db.commit()
    await db.refresh(obj)
    return ExpenseRead.model_validate(obj)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Void expense (soft delete)")
async def void_expense(expense_id: uuid.UUID, cu: AuthUser, db: DbSession) -> None:
    cu.require_role("super_admin", "finance_hr")
    obj = await _get_or_404(db, cu.tenant_id, expense_id)
    if obj.status == "posted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot void a posted expense.")
    if obj.status == "void":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Expense already void.")
    obj.status = "void"
    await db.flush()
    await log_event(db, tenant_id=cu.tenant_id, actor_user_id=cu.user_id,
                    action="void", entity_type="expenses", entity_id=obj.id)
    await db.commit()
