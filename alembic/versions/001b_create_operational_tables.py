"""Gate 1b — Create operational tables: employees, projects, timesheets, invoices, payroll_runs

Revision ID: 001b
Revises: 001
Create Date: 2026-03-29

These tables were assumed to pre-exist by migration 002 (Gate 2).
This migration creates them from scratch on a clean database.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001b"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) employees ──────────────────────────────────────────────────────────
    # Note: tenant_id is intentionally omitted here — migration 002 adds it.
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("employee_number", sa.String(20), nullable=False, unique=True),
        sa.Column("full_name_en", sa.String(200), nullable=False),
        sa.Column("full_name_ar", sa.String(200), nullable=True),
        sa.Column("nationality", sa.String(60), nullable=False),
        sa.Column("iqama_number", sa.String(20), nullable=True, unique=True),
        sa.Column("iqama_expiry_date", sa.Date(), nullable=True),
        sa.Column("passport_number", sa.String(30), nullable=True),
        sa.Column("passport_expiry_date", sa.Date(), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("employment_type", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("probation_end_date", sa.Date(), nullable=True),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("basic_salary_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("housing_allowance_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("transport_allowance_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("other_allowances_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("gosi_enrolled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gosi_number", sa.String(30), nullable=True),
        sa.Column("saudi_iban", sa.String(34), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_employees_status", "employees", ["status"])
    op.create_index("ix_employees_iqama_expiry", "employees", ["iqama_expiry_date"])
    op.create_index("ix_employees_nationality", "employees", ["nationality"])
    op.create_index("ix_employees_department", "employees", ["department"])

    # ── 2) projects ───────────────────────────────────────────────────────────
    # Note: tenant_id, client_id, po_id are omitted here — migration 002 adds them.
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_number", sa.String(20), nullable=False, unique=True),
        sa.Column("name_en", sa.String(300), nullable=False),
        sa.Column("name_ar", sa.String(300), nullable=True),
        sa.Column("client_name", sa.String(300), nullable=False),
        sa.Column("po_number", sa.String(100), nullable=True),
        sa.Column("po_value_sar", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("contract_value_sar", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_manager_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_client", "projects", ["client_name"])
    op.create_index("ix_projects_po_number", "projects", ["po_number"])

    # ── 3) timesheets ─────────────────────────────────────────────────────────
    # Note: tenant_id is omitted here — migration 002 adds it.
    op.create_table(
        "timesheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("timesheet_number", sa.String(20), nullable=False, unique=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("hours_sun", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("hours_mon", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("hours_tue", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("hours_wed", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("hours_thu", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("hours_fri", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("hours_sat", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_timesheets_employee", "timesheets", ["employee_id"])
    op.create_index("ix_timesheets_project", "timesheets", ["project_id"])
    op.create_index("ix_timesheets_status", "timesheets", ["status"])
    op.create_index("ix_timesheets_week", "timesheets", ["week_start_date"])

    # ── 4) invoices ───────────────────────────────────────────────────────────
    # Note: tenant_id and po_id are omitted here — migration 002 adds them.
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("invoice_number", sa.String(30), nullable=False, unique=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_name", sa.String(300), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("subtotal_sar", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("vat_rate", sa.Numeric(5, 4), nullable=False, server_default="0.1500"),
        sa.Column("vat_amount_sar", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_sar", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("gl_posted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gl_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gl_entry_ref", sa.String(100), nullable=True),
        sa.Column("zatca_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("zatca_uuid", sa.String(100), nullable=True),
        sa.Column("zatca_hash", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_project", "invoices", ["project_id"])
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])
    op.create_index("ix_invoices_zatca_status", "invoices", ["zatca_status"])

    # ── 5) payroll_runs ───────────────────────────────────────────────────────
    # Note: tenant_id is omitted here — migration 002 adds it.
    op.create_table(
        "payroll_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("payroll_number", sa.String(30), nullable=False, unique=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pay_period_start", sa.Date(), nullable=False),
        sa.Column("pay_period_end", sa.Date(), nullable=False),
        sa.Column("basic_salary_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("housing_allowance_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("transport_allowance_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("other_allowances_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("gross_salary_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("gosi_employee_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("gosi_employer_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("other_deductions_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("net_salary_sar", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wps_file_ref", sa.String(100), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("bank_transfer_ref", sa.String(100), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_employee", "payroll_runs", ["employee_id"])
    op.create_index("ix_payroll_status", "payroll_runs", ["status"])
    op.create_index("ix_payroll_period", "payroll_runs", ["pay_period_start", "pay_period_end"])


def downgrade() -> None:
    op.drop_table("payroll_runs")
    op.drop_table("invoices")
    op.drop_table("timesheets")
    op.drop_table("projects")
    op.drop_table("employees")
