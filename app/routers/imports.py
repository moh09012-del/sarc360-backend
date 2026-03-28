"""
SARC360 ERP — Import/Export Router
نقاط نهاية استيراد وتصدير Excel
"""
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AuthUser, DbSession
from app.core.database import get_db
from app.services.excel_service import (
    create_employees_template,
    create_clients_template,
    create_projects_template,
    create_timesheets_template,
    create_expenses_template,
)
from app.services.import_service import (
    import_employees_excel,
    import_clients_excel,
    import_projects_excel,
    import_timesheets_excel,
    import_expenses_excel,
)
from fastapi.responses import StreamingResponse
import io

router = APIRouter(prefix="/import", tags=["Import/Export"])


# ═══════════════════════════════════════════════════════════
# TEMPLATE DOWNLOADS
# ═══════════════════════════════════════════════════════════


@router.get("/templates/employees", summary="Download employees template")
async def download_employees_template():
    """Download Employees import template (Excel)."""
    content = create_employees_template()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=employees_template.xlsx"},
    )


@router.get("/templates/clients", summary="Download clients template")
async def download_clients_template():
    """Download Clients import template (Excel)."""
    content = create_clients_template()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=clients_template.xlsx"},
    )


@router.get("/templates/projects", summary="Download projects template")
async def download_projects_template():
    """Download Projects import template (Excel)."""
    content = create_projects_template()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=projects_template.xlsx"},
    )


@router.get("/templates/timesheets", summary="Download timesheets template")
async def download_timesheets_template():
    """Download Timesheets import template (Excel)."""
    content = create_timesheets_template()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=timesheets_template.xlsx"},
    )


@router.get("/templates/expenses", summary="Download expenses template")
async def download_expenses_template():
    """Download Expenses import template (Excel)."""
    content = create_expenses_template()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=expenses_template.xlsx"},
    )


# ═══════════════════════════════════════════════════════════
# BULK IMPORTS
# ═══════════════════════════════════════════════════════════


@router.post("/employees", summary="Import employees from Excel")
async def import_employees(
    file: UploadFile = File(...),
    cu: AuthUser = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload employees.xlsx to import multiple employees.
    
    Response:
    {
        "total_rows": 10,
        "success_rows": 9,
        "failed_rows": 1,
        "errors": [
            {
                "row": 5,
                "error": "Invalid salary format",
                "values": {...}
            }
        ]
    }
    """
    try:
        content = await file.read()
        result = await import_employees_excel(db, content, cu.tenant_id if cu else None, cu.user_id if cu else None)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/clients", summary="Import clients from Excel")
async def import_clients(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload clients.xlsx to import multiple clients."""
    try:
        content = await file.read()
        # For now, use a default tenant/user. In production, get from AuthUser
        result = await import_clients_excel(db, content, None, None)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/projects", summary="Import projects from Excel")
async def import_projects(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload projects.xlsx to import multiple projects."""
    try:
        content = await file.read()
        result = await import_projects_excel(db, content, None, None)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/timesheets", summary="Import timesheets from Excel")
async def import_timesheets(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload timesheets.xlsx to import multiple timesheets."""
    try:
        content = await file.read()
        result = await import_timesheets_excel(db, content, None, None)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/expenses", summary="Import expenses from Excel")
async def import_expenses(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload expenses.xlsx to import multiple expenses."""
    try:
        content = await file.read()
        result = await import_expenses_excel(db, content, None, None)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )
