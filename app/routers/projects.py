"""
SARC360 ERP - Projects Router
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}  (soft — sets status=cancelled)
"""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthUser, DbSession
from app.crud.project import project_crud
from app.models.project import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectRead,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse, summary="List projects")
async def list_projects(
    cu: AuthUser,
    db: DbSession,
    status: str | None = Query(None, description="active | completed | on_hold | cancelled"),
    department: str | None = Query(None),
    search: str | None = Query(None, description="Search by name, client, or PO number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ProjectListResponse:
    query = select(Project).where(Project.tenant_id == cu.tenant_id)
    if status:
        query = query.where(Project.status == status)
    if department:
        query = query.where(Project.department == department)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Project.name_en.ilike(pattern),
                Project.name_ar.ilike(pattern),
                Project.client_name.ilike(pattern),
                Project.po_number.ilike(pattern),
                Project.project_number.ilike(pattern),
            )
        )
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total: int = count_result.scalar_one()
    offset = (page - 1) * page_size
    query = query.order_by(Project.project_number).offset(offset).limit(page_size)
    rows = await db.execute(query)
    projects = list(rows.scalars().all())
    pages = math.ceil(total / page_size) if total else 1
    return ProjectListResponse(
        items=[ProjectRead.model_validate(p) for p in projects],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Create project")
async def create_project(
    payload: ProjectCreate,
    cu: AuthUser,
    db: DbSession,
) -> ProjectRead:
    # Auto-generate project_number
    count_res = await db.execute(select(func.count()).select_from(Project).where(Project.tenant_id == cu.tenant_id))
    count = count_res.scalar_one()
    project_number = f"PRJ-{count + 1:03d}"

    project = Project(
        **payload.model_dump(),
        project_number=project_number,
        tenant_id=cu.tenant_id,
        created_by=cu.user_id,
    )
    db.add(project)
    await db.flush()
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead, summary="Get project by ID")
async def get_project(
    project_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> ProjectRead:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == cu.tenant_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead, summary="Update project")
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    cu: AuthUser,
    db: DbSession,
) -> ProjectRead:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == cu.tenant_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.updated_by = cu.user_id
    await db.flush()
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel project (soft delete)")
async def cancel_project(
    project_id: uuid.UUID,
    cu: AuthUser,
    db: DbSession,
) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == cu.tenant_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if project.status == "cancelled":
        raise HTTPException(status_code=409, detail="Project is already cancelled.")
    project.status = "cancelled"
    project.updated_by = cu.user_id
    await db.flush()
    await db.commit()
