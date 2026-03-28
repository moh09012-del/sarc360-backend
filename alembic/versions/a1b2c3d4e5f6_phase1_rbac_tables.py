"""phase1_rbac_tables

Revision ID: a1b2c3d4e5f6
Revises: 67395b656de2
Create Date: 2026-03-28 10:00:00.000000+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '67395b656de2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── permission_templates ──────────────────────────────────────────────────
    op.create_table(
        'permission_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_code', sa.String(length=50), nullable=False,
                  comment='Matches roles.code'),
        sa.Column('module', sa.String(length=50), nullable=False,
                  comment='e.g. invoices, payroll, employees'),
        sa.Column('can_view',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_create',  sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_edit',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_approve', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_post',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_export',  sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_code', 'module', name='uq_perm_role_module'),
    )
    op.create_index('ix_perm_role', 'permission_templates', ['role_code'])

    # ── user_permission_overrides ─────────────────────────────────────────────
    op.create_table(
        'user_permission_overrides',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False,
                  comment='view | create | edit | approve | post | export'),
        sa.Column('granted', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True,
                  comment='NULL = permanent override'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_perm_override_user',   'user_permission_overrides', ['tenant_id', 'user_id'])
    op.create_index('ix_perm_override_expiry', 'user_permission_overrides', ['expires_at'])

    # ── user_project_assignments ──────────────────────────────────────────────
    op.create_table(
        'user_project_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', 'project_id', name='uq_user_project'),
    )
    op.create_index('ix_user_project_user',    'user_project_assignments', ['tenant_id', 'user_id'])
    op.create_index('ix_user_project_project', 'user_project_assignments', ['tenant_id', 'project_id'])

    # ── Seed 9 enterprise role codes ──────────────────────────────────────────
    op.execute("""
        INSERT INTO roles (id, code, name) VALUES
          (gen_random_uuid(), 'general_manager',        'General Manager'),
          (gen_random_uuid(), 'finance_manager',        'Finance Manager'),
          (gen_random_uuid(), 'accountant',             'Accountant'),
          (gen_random_uuid(), 'hr_manager',             'HR Manager'),
          (gen_random_uuid(), 'payroll_officer',        'Payroll Officer'),
          (gen_random_uuid(), 'bd_manager',             'Business Development Manager'),
          (gen_random_uuid(), 'project_manager',        'Project Manager'),
          (gen_random_uuid(), 'operations_coordinator', 'Operations Coordinator'),
          (gen_random_uuid(), 'auditor',                'Auditor')
        ON CONFLICT (code) DO NOTHING;
    """)

    # ── Seed permission_templates ─────────────────────────────────────────────
    # Format: (role_code, module, view, create, edit, approve, post, export)
    op.execute("""
        INSERT INTO permission_templates
          (id, role_code, module, can_view, can_create, can_edit, can_approve, can_post, can_export)
        VALUES

        -- super_admin: full access to everything
        (gen_random_uuid(), 'super_admin', 'employees',  true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'projects',   true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'timesheets', true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'invoices',   true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'contracts',  true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'clients',    true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'expenses',   true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'payroll',    true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'suppliers',  true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'cost_engine',true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'dashboard',  true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'imports',    true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'users',      true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'audit_log',  true, true, true, true, true, true),
        (gen_random_uuid(), 'super_admin', 'settings',   true, true, true, true, true, true),

        -- general_manager: view all, no payroll/settings edit
        (gen_random_uuid(), 'general_manager', 'employees',  true, false, false, true,  false, true),
        (gen_random_uuid(), 'general_manager', 'projects',   true, true,  true,  true,  false, true),
        (gen_random_uuid(), 'general_manager', 'timesheets', true, false, false, true,  false, true),
        (gen_random_uuid(), 'general_manager', 'invoices',   true, false, false, true,  true,  true),
        (gen_random_uuid(), 'general_manager', 'contracts',  true, true,  true,  true,  false, true),
        (gen_random_uuid(), 'general_manager', 'clients',    true, true,  true,  false, false, true),
        (gen_random_uuid(), 'general_manager', 'expenses',   true, false, false, true,  false, true),
        (gen_random_uuid(), 'general_manager', 'payroll',    true, false, false, true,  false, true),
        (gen_random_uuid(), 'general_manager', 'suppliers',  true, false, false, false, false, true),
        (gen_random_uuid(), 'general_manager', 'cost_engine',true, false, false, false, false, true),
        (gen_random_uuid(), 'general_manager', 'dashboard',  true, false, false, false, false, true),
        (gen_random_uuid(), 'general_manager', 'imports',    false,false, false, false, false, false),
        (gen_random_uuid(), 'general_manager', 'users',      true, false, false, false, false, false),
        (gen_random_uuid(), 'general_manager', 'audit_log',  true, false, false, false, false, true),
        (gen_random_uuid(), 'general_manager', 'settings',   true, false, false, false, false, false),

        -- finance_hr (legacy role): finance + HR combined
        (gen_random_uuid(), 'finance_hr', 'employees',  true, true, true,  false, false, true),
        (gen_random_uuid(), 'finance_hr', 'projects',   true, false,false, false, false, true),
        (gen_random_uuid(), 'finance_hr', 'timesheets', true, false,false, true,  false, true),
        (gen_random_uuid(), 'finance_hr', 'invoices',   true, true, true,  false, true,  true),
        (gen_random_uuid(), 'finance_hr', 'contracts',  true, true, true,  false, false, true),
        (gen_random_uuid(), 'finance_hr', 'clients',    true, true, true,  false, false, true),
        (gen_random_uuid(), 'finance_hr', 'expenses',   true, true, true,  true,  false, true),
        (gen_random_uuid(), 'finance_hr', 'payroll',    true, true, true,  true,  false, true),
        (gen_random_uuid(), 'finance_hr', 'suppliers',  true, true, true,  false, false, true),
        (gen_random_uuid(), 'finance_hr', 'cost_engine',true, true, true,  false, false, true),
        (gen_random_uuid(), 'finance_hr', 'dashboard',  true, false,false, false, false, true),
        (gen_random_uuid(), 'finance_hr', 'imports',    true, true, false, false, false, false),
        (gen_random_uuid(), 'finance_hr', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'finance_hr', 'audit_log',  true, false,false, false, false, true),
        (gen_random_uuid(), 'finance_hr', 'settings',   false,false,false, false, false, false),

        -- finance_manager: full finance access, limited HR
        (gen_random_uuid(), 'finance_manager', 'employees',  true, false, false, false, false, true),
        (gen_random_uuid(), 'finance_manager', 'projects',   true, false, false, false, false, true),
        (gen_random_uuid(), 'finance_manager', 'timesheets', true, false, false, true,  false, true),
        (gen_random_uuid(), 'finance_manager', 'invoices',   true, true,  true,  true,  true,  true),
        (gen_random_uuid(), 'finance_manager', 'contracts',  true, true,  true,  true,  false, true),
        (gen_random_uuid(), 'finance_manager', 'clients',    true, true,  true,  false, false, true),
        (gen_random_uuid(), 'finance_manager', 'expenses',   true, true,  true,  true,  false, true),
        (gen_random_uuid(), 'finance_manager', 'payroll',    true, true,  true,  true,  false, true),
        (gen_random_uuid(), 'finance_manager', 'suppliers',  true, true,  true,  false, false, true),
        (gen_random_uuid(), 'finance_manager', 'cost_engine',true, true,  true,  false, false, true),
        (gen_random_uuid(), 'finance_manager', 'dashboard',  true, false, false, false, false, true),
        (gen_random_uuid(), 'finance_manager', 'imports',    true, true,  false, false, false, false),
        (gen_random_uuid(), 'finance_manager', 'users',      false,false, false, false, false, false),
        (gen_random_uuid(), 'finance_manager', 'audit_log',  true, false, false, false, false, true),
        (gen_random_uuid(), 'finance_manager', 'settings',   false,false, false, false, false, false),

        -- accountant: view + create in finance, no approve/post
        (gen_random_uuid(), 'accountant', 'employees',  true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'projects',   true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'timesheets', true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'invoices',   true, true,  true,  false, false, true),
        (gen_random_uuid(), 'accountant', 'contracts',  true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'clients',    true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'expenses',   true, true,  true,  false, false, true),
        (gen_random_uuid(), 'accountant', 'payroll',    true, false, false, false, false, false),
        (gen_random_uuid(), 'accountant', 'suppliers',  true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'cost_engine',true, false, false, false, false, false),
        (gen_random_uuid(), 'accountant', 'dashboard',  true, false, false, false, false, true),
        (gen_random_uuid(), 'accountant', 'imports',    true, true,  false, false, false, false),
        (gen_random_uuid(), 'accountant', 'users',      false,false, false, false, false, false),
        (gen_random_uuid(), 'accountant', 'audit_log',  false,false, false, false, false, false),
        (gen_random_uuid(), 'accountant', 'settings',   false,false, false, false, false, false),

        -- hr_manager: full employee/payroll access, limited finance view
        (gen_random_uuid(), 'hr_manager', 'employees',  true, true, true,  true,  false, true),
        (gen_random_uuid(), 'hr_manager', 'projects',   true, false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'timesheets', true, false,false, false, false, true),
        (gen_random_uuid(), 'hr_manager', 'invoices',   false,false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'contracts',  false,false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'clients',    false,false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'expenses',   true, false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'payroll',    true, true, true,  true,  false, true),
        (gen_random_uuid(), 'hr_manager', 'suppliers',  false,false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'dashboard',  true, false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'imports',    true, true, false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'users',      true, true, false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'hr_manager', 'settings',   false,false,false, false, false, false),

        -- payroll_officer: payroll only
        (gen_random_uuid(), 'payroll_officer', 'employees',  true, false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'projects',   false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'timesheets', true, false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'invoices',   false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'contracts',  false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'clients',    false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'expenses',   false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'payroll',    true, true, true,  false, false, true),
        (gen_random_uuid(), 'payroll_officer', 'suppliers',  false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'dashboard',  false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'payroll_officer', 'settings',   false,false,false, false, false, false),

        -- bd_manager: clients, contracts, limited projects view
        (gen_random_uuid(), 'bd_manager', 'employees',  false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'projects',   true, true, true,  false, false, true),
        (gen_random_uuid(), 'bd_manager', 'timesheets', false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'invoices',   true, false,false, false, false, true),
        (gen_random_uuid(), 'bd_manager', 'contracts',  true, true, true,  false, false, true),
        (gen_random_uuid(), 'bd_manager', 'clients',    true, true, true,  false, false, true),
        (gen_random_uuid(), 'bd_manager', 'expenses',   false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'payroll',    false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'suppliers',  true, false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'dashboard',  true, false,false, false, false, true),
        (gen_random_uuid(), 'bd_manager', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'bd_manager', 'settings',   false,false,false, false, false, false),

        -- project_manager: scoped to assigned projects only (enforced in queries)
        (gen_random_uuid(), 'project_manager', 'employees',  true, false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'projects',   true, false,true,  false, false, true),
        (gen_random_uuid(), 'project_manager', 'timesheets', true, true, true,  true,  false, true),
        (gen_random_uuid(), 'project_manager', 'invoices',   true, false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'contracts',  true, false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'clients',    true, false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'expenses',   true, true, true,  false, false, true),
        (gen_random_uuid(), 'project_manager', 'payroll',    false,false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'suppliers',  true, false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'dashboard',  true, false,false, false, false, true),
        (gen_random_uuid(), 'project_manager', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'project_manager', 'settings',   false,false,false, false, false, false),

        -- operations_coordinator: scoped to assigned projects, limited actions
        (gen_random_uuid(), 'operations_coordinator', 'employees',  true, false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'projects',   true, false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'timesheets', true, true, true,  false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'invoices',   false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'contracts',  true, false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'clients',    true, false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'expenses',   true, true, false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'payroll',    false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'suppliers',  true, false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'dashboard',  false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'operations_coordinator', 'settings',   false,false,false, false, false, false),

        -- auditor: read-only everywhere + export
        (gen_random_uuid(), 'auditor', 'employees',  true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'projects',   true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'timesheets', true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'invoices',   true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'contracts',  true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'clients',    true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'expenses',   true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'payroll',    true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'suppliers',  true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'cost_engine',true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'dashboard',  true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'auditor', 'users',      true, false,false, false, false, false),
        (gen_random_uuid(), 'auditor', 'audit_log',  true, false,false, false, false, true),
        (gen_random_uuid(), 'auditor', 'settings',   false,false,false, false, false, false),

        -- projects (legacy role): same as project_manager
        (gen_random_uuid(), 'projects', 'employees',  true, false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'projects',   true, true, true,  false, false, true),
        (gen_random_uuid(), 'projects', 'timesheets', true, true, true,  true,  false, true),
        (gen_random_uuid(), 'projects', 'invoices',   true, false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'contracts',  true, false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'clients',    true, false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'expenses',   true, true, true,  false, false, true),
        (gen_random_uuid(), 'projects', 'payroll',    false,false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'suppliers',  true, false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'dashboard',  true, false,false, false, false, true),
        (gen_random_uuid(), 'projects', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'projects', 'settings',   false,false,false, false, false, false),

        -- employee (legacy role): own timesheets only
        (gen_random_uuid(), 'employee', 'employees',  true, false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'projects',   true, false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'timesheets', true, true, false, false, false, false),
        (gen_random_uuid(), 'employee', 'invoices',   false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'contracts',  false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'clients',    false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'expenses',   false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'payroll',    false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'suppliers',  false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'dashboard',  false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'employee', 'settings',   false,false,false, false, false, false),

        -- client (legacy role): view their invoices/contracts only
        (gen_random_uuid(), 'client', 'employees',  false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'projects',   true, false,false, false, false, false),
        (gen_random_uuid(), 'client', 'timesheets', false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'invoices',   true, false,false, false, false, false),
        (gen_random_uuid(), 'client', 'contracts',  true, false,false, false, false, false),
        (gen_random_uuid(), 'client', 'clients',    false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'expenses',   false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'payroll',    false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'suppliers',  false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'cost_engine',false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'dashboard',  false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'imports',    false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'users',      false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'audit_log',  false,false,false, false, false, false),
        (gen_random_uuid(), 'client', 'settings',   false,false,false, false, false, false)

        ON CONFLICT (role_code, module) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_index('ix_user_project_project', table_name='user_project_assignments')
    op.drop_index('ix_user_project_user',    table_name='user_project_assignments')
    op.drop_table('user_project_assignments')

    op.drop_index('ix_perm_override_expiry', table_name='user_permission_overrides')
    op.drop_index('ix_perm_override_user',   table_name='user_permission_overrides')
    op.drop_table('user_permission_overrides')

    op.drop_index('ix_perm_role', table_name='permission_templates')
    op.drop_table('permission_templates')
