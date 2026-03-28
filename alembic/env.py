"""Alembic environment — async SQLAlchemy (asyncpg) setup."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import Base

# ── Import ALL models so SQLAlchemy registers them with Base.metadata ─────────
from app.models import *  # noqa: F401, F403
from app.models.tenant import Tenant, Role, UserRole
from app.models.user import User, AuthVerificationCode, AuthRateLimit
from app.models.client import Client
from app.models.contract import Contract
from app.models.supplier import Supplier
from app.models.expense import Expense
from app.models.cost_engine import EmployeePayRate, TimesheetCost
from app.models.project_pl import ProjectPLPeriod
from app.models.audit import AuditEvent

# ─────────────────────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via run_sync."""
    connectable = create_async_engine(settings.DATABASE_URL, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
