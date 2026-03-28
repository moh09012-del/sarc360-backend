"""Gate 2 — Add tenant_id / client_id / po_id to existing tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SARC_TENANT_UUID = "00000001-0000-0000-0000-000000000001"


def _add_tenant_id(table: str, index_name: str) -> None:
    """Add tenant_id (nullable → backfill → NOT NULL) + index."""
    op.add_column(table, sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE {table} SET tenant_id = '{SARC_TENANT_UUID}' WHERE tenant_id IS NULL")
    op.alter_column(table, "tenant_id", nullable=False)
    op.create_index(index_name, table, ["tenant_id", "id"])


def upgrade() -> None:
    # ── A) employees ──────────────────────────────────────────────────────────
    # tenant_id column already defined in the model; add via migration
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE employees SET tenant_id = '{SARC_TENANT_UUID}' WHERE tenant_id IS NULL")
    op.alter_column("employees", "tenant_id", nullable=False)
    op.create_index("ix_employees_tenant", "employees", ["tenant_id", "id"])

    # ── B) projects ───────────────────────────────────────────────────────────
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("po_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE projects SET tenant_id = '{SARC_TENANT_UUID}' WHERE tenant_id IS NULL")
    op.alter_column("projects", "tenant_id", nullable=False)
    op.create_index("ix_projects_tenant", "projects", ["tenant_id", "id"])
    op.create_index("ix_projects_client_id", "projects", ["tenant_id", "client_id"])
    op.create_index("ix_projects_po_id", "projects", ["tenant_id", "po_id"])

    # ── C) timesheets ─────────────────────────────────────────────────────────
    with op.batch_alter_table("timesheets") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE timesheets SET tenant_id = '{SARC_TENANT_UUID}' WHERE tenant_id IS NULL")
    op.alter_column("timesheets", "tenant_id", nullable=False)
    op.create_index("ix_timesheets_tenant", "timesheets", ["tenant_id", "id"])

    # ── D) invoices ───────────────────────────────────────────────────────────
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("po_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE invoices SET tenant_id = '{SARC_TENANT_UUID}' WHERE tenant_id IS NULL")
    op.alter_column("invoices", "tenant_id", nullable=False)
    op.create_index("ix_invoices_tenant", "invoices", ["tenant_id", "id"])
    op.create_index("ix_invoices_po", "invoices", ["tenant_id", "po_id"])

    # ── E) payroll_runs ───────────────────────────────────────────────────────
    with op.batch_alter_table("payroll_runs") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE payroll_runs SET tenant_id = '{SARC_TENANT_UUID}' WHERE tenant_id IS NULL")
    op.alter_column("payroll_runs", "tenant_id", nullable=False)
    op.create_index("ix_payroll_tenant", "payroll_runs", ["tenant_id", "id"])


def downgrade() -> None:
    for idx in ["ix_payroll_tenant"]:
        op.drop_index(idx, table_name="payroll_runs")
    op.drop_column("payroll_runs", "tenant_id")

    for idx in ["ix_invoices_tenant", "ix_invoices_po"]:
        op.drop_index(idx, table_name="invoices")
    op.drop_column("invoices", "po_id")
    op.drop_column("invoices", "tenant_id")

    for idx in ["ix_timesheets_tenant"]:
        op.drop_index(idx, table_name="timesheets")
    op.drop_column("timesheets", "tenant_id")

    for idx in ["ix_projects_tenant", "ix_projects_client_id", "ix_projects_po_id"]:
        op.drop_index(idx, table_name="projects")
    op.drop_column("projects", "po_id")
    op.drop_column("projects", "client_id")
    op.drop_column("projects", "tenant_id")

    for idx in ["ix_employees_tenant"]:
        op.drop_index(idx, table_name="employees")
    op.drop_column("employees", "tenant_id")
