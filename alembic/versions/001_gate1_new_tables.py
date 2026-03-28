"""Gate 1 — New tables: tenants, roles, users, clients, contracts, suppliers, expenses, cost_engine, pl, audit

Revision ID: 001
Revises:
Create Date: 2026-03-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed UUID for the default SARC tenant used across all environments
SARC_TENANT_UUID = "00000001-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ── 0) Extensions ─────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── 1) Tenants ─────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("legal_name", sa.String(300), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(10), nullable=True, server_default="SA"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── 2) Roles ───────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
    )

    # ── 3) Users ───────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(300), nullable=False),
        sa.Column("user_type", sa.String(20), nullable=False, server_default="staff"),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_phone_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_tenant", "users", ["tenant_id", "id"])
    op.create_unique_constraint("ux_users_email", "users", ["tenant_id", "email"])

    # ── 4) User Roles ──────────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", "role_id"),
    )
    op.create_index("ix_user_roles_user", "user_roles", ["tenant_id", "user_id"])

    # ── 5) Auth Verification Codes ─────────────────────────────────────────────
    op.create_table(
        "auth_verification_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_codes_lookup", "auth_verification_codes", ["tenant_id", "user_id", "channel", "purpose", "expires_at"])

    # ── 6) Auth Rate Limits ────────────────────────────────────────────────────
    op.create_table(
        "auth_rate_limits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("key_type", sa.String(20), nullable=False),
        sa.Column("key_value", sa.String(255), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rate_limits_key", "auth_rate_limits", ["key_type", "key_value", "window_start"])

    # ── 7) Clients ─────────────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name_en", sa.String(300), nullable=False),
        sa.Column("name_ar", sa.String(300), nullable=True),
        sa.Column("cr_number", sa.String(50), nullable=True),
        sa.Column("vat_number", sa.String(50), nullable=True),
        sa.Column("billing_email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address_line1", sa.String(400), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(10), nullable=False, server_default="SA"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("ux_clients_name_per_tenant", "clients", ["tenant_id", "name_en"])
    op.create_index("ix_clients_tenant", "clients", ["tenant_id", "id"])

    # ── 8) Contracts / POs ─────────────────────────────────────────────────────
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("po_number", sa.String(100), nullable=False),
        sa.Column("title", sa.String(400), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("total_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("total_value >= 0", name="ck_contracts_total_value"),
    )
    op.create_unique_constraint("ux_contracts_po_per_client", "contracts", ["tenant_id", "client_id", "po_number"])
    op.create_index("ix_contracts_tenant", "contracts", ["tenant_id", "id"])
    op.create_index("ix_contracts_client", "contracts", ["tenant_id", "client_id"])

    # ── 9) Suppliers ───────────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("supplier_type", sa.String(30), nullable=False),
        sa.Column("vat_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", sa.String(400), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("ux_suppliers_name_per_tenant", "suppliers", ["tenant_id", "name"])
    op.create_index("ix_suppliers_tenant", "suppliers", ["tenant_id", "id"])

    # ── 10) Expenses ───────────────────────────────────────────────────────────
    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount_net", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("amount_gross", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("gl_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_net >= 0", name="ck_expenses_amount_net"),
        sa.CheckConstraint("vat_amount >= 0", name="ck_expenses_vat_amount"),
    )
    op.create_index("ix_expenses_project", "expenses", ["tenant_id", "project_id", "expense_date"])
    op.create_index("ix_expenses_supplier", "expenses", ["tenant_id", "supplier_id"])

    # ── 11) Employee Pay Rates ─────────────────────────────────────────────────
    op.create_table(
        "employee_pay_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("monthly_gross_salary", sa.Numeric(18, 2), nullable=False),
        sa.Column("employer_cost_rate", sa.Numeric(6, 4), nullable=False, server_default="0.0000"),
        sa.Column("standard_monthly_hours", sa.Numeric(10, 2), nullable=False, server_default="240"),
        sa.Column("hourly_cost", sa.Numeric(18, 6), nullable=False, server_default="0.000000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("monthly_gross_salary >= 0", name="ck_pay_rates_salary"),
        sa.CheckConstraint("employer_cost_rate >= 0", name="ck_pay_rates_cost_rate"),
        sa.CheckConstraint("standard_monthly_hours > 0", name="ck_pay_rates_hours"),
    )
    op.create_index("ix_employee_rates_lookup", "employee_pay_rates", ["tenant_id", "employee_id", "effective_from", "effective_to"])

    # ── 12) Timesheet Costs ────────────────────────────────────────────────────
    op.create_table(
        "timesheet_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("timesheet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_rate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee_pay_rates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("hourly_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("costed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("costed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("hours >= 0", name="ck_ts_costs_hours"),
        sa.CheckConstraint("cost_amount >= 0", name="ck_ts_costs_amount"),
    )
    op.create_unique_constraint("ux_timesheet_costs_timesheet", "timesheet_costs", ["tenant_id", "timesheet_id"])

    # ── 13) Project P&L Periods ────────────────────────────────────────────────
    op.create_table(
        "project_pl_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("revenue_net", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("labor_cost", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vendor_cost", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("overhead_allocated", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("gross_profit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_profit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("billable_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("utilization_rate", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("computed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "project_id", "period_start", "period_end", name="ux_pl_period"),
    )
    op.create_index("ix_pl_project_period", "project_pl_periods", ["tenant_id", "project_id", "period_start", "period_end"])

    # ── 14) Audit Events ───────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("before_data", postgresql.JSON(), nullable=True),
        sa.Column("after_data", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_tenant_time", "audit_events", ["tenant_id", "created_at"])
    op.create_index("ix_audit_entity", "audit_events", ["tenant_id", "entity_type", "entity_id"])

    # ── Seed: default tenant + roles ──────────────────────────────────────────
    op.execute(f"""
        INSERT INTO tenants (id, slug, legal_name, city, country, max_users, is_active)
        VALUES (
            '{SARC_TENANT_UUID}',
            'sarc-001',
            'شركة سما الروابي للمقاولات',
            'الخبر',
            'SA',
            100,
            true
        )
        ON CONFLICT (slug) DO NOTHING
    """)

    op.execute("""
        INSERT INTO roles (id, code, name) VALUES
            (gen_random_uuid(), 'super_admin', 'Super Administrator'),
            (gen_random_uuid(), 'finance_hr',  'Finance & HR Manager'),
            (gen_random_uuid(), 'projects',    'Projects Manager'),
            (gen_random_uuid(), 'employee',    'Employee'),
            (gen_random_uuid(), 'client',      'Client Portal')
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("project_pl_periods")
    op.drop_table("timesheet_costs")
    op.drop_table("employee_pay_rates")
    op.drop_table("expenses")
    op.drop_table("suppliers")
    op.drop_table("contracts")
    op.drop_table("clients")
    op.drop_table("auth_rate_limits")
    op.drop_table("auth_verification_codes")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("tenants")
