"""
SARC360 ERP - FastAPI Application Entry Point
شركة سما الروابي للمقاولات - الخبر

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_all_tables
import app.models  # noqa: F401 — registers all models with Base.metadata
from app.routers import (
    auth,
    clients,
    contracts,
    cost_engine,
    dashboard,
    employees,
    expenses,
    imports,
    invoices,
    payroll,
    projects,
    rbac,
    suppliers,
    timesheets,
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    # Skip table creation on every startup (use Alembic instead)
    # Only verify database connection is working
    yield
    # Shutdown: nothing to clean up for now


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "ERP backend for **Sama Al Rawabi Contracting Co.** (شركة سما الروابي للمقاولات), "
        "Al-Khobar, Saudi Arabia.\n\n"
        "Covers: Employees · Projects · Timesheets · Invoicing (ZATCA Phase 2) · "
        "Payroll (WPS/Mudad) · HR · Finance."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"null",   # allow file:// origin in dev
)


# ── Routers ───────────────────────────────────────────────────────────────────
API_V1 = "/api/v1"

app.include_router(employees.router,     prefix=API_V1)
app.include_router(projects.router,      prefix=API_V1)
app.include_router(timesheets.router,    prefix=API_V1)
app.include_router(invoices.router,      prefix=API_V1)
app.include_router(payroll.router,       prefix=API_V1)
# Gates 3–8
app.include_router(clients.router,       prefix=API_V1)
app.include_router(contracts.router,     prefix=API_V1)
app.include_router(suppliers.router,     prefix=API_V1)
app.include_router(expenses.router,      prefix=API_V1)
app.include_router(cost_engine.router,   prefix=API_V1)
app.include_router(dashboard.router,     prefix=API_V1)
app.include_router(imports.router,       prefix=API_V1)
app.include_router(rbac.router,          prefix=API_V1)
app.include_router(auth.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    from sqlalchemy import text
    from app.core.database import engine

    db_status = "ok"
    db_error = None
    migration_version = None

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            # Check Alembic migration head
            try:
                result = await conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                row = result.fetchone()
                migration_version = row[0] if row else "unknown"
            except Exception:
                migration_version = "unknown"
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)

    response = {
        "status": "ok" if db_status == "ok" else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "db": db_status,
        "migration": migration_version,
    }
    if db_error:
        response["db_error"] = db_error
    return response
