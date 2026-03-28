"""
SARC360 ERP - Project CRUD
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectCRUD:

    async def _next_number(self, db: AsyncSession) -> str:
        result = await db.execute(select(func.count()).select_from(Project))
        count: int = result.scalar_one()
        return f"PRJ-{count + 1:03d}"

    async def create(
        self, db: AsyncSession, payload: ProjectCreate,
        created_by: uuid.UUID | None = None,
    ) -> Project:
        project = Project(
            **payload.model_dump(),
            project_number=await self._next_number(db),
            created_by=created_by,
        )
        db.add(project)
        await db.flush()
        await db.refresh(project)
        return project

    async def get(self, db: AsyncSession, project_id: uuid.UUID) -> Project | None:
        result = await db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def list(
        self, db: AsyncSession, *,
        status: str | None = None,
        department: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Project], int]:
        query = select(Project)
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
        return list(rows.scalars().all()), total

    async def update(
        self, db: AsyncSession, project: Project, payload: ProjectUpdate,
        updated_by: uuid.UUID | None = None,
    ) -> Project:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        if updated_by:
            project.updated_by = updated_by
        await db.flush()
        await db.refresh(project)
        return project


project_crud = ProjectCRUD()
