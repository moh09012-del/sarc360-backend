# Import all models so SQLAlchemy registers them with Base.metadata
# Existing models
from app.models.employee import Employee
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.models.invoice import Invoice
from app.models.payroll import PayrollRun

# New models — Gates 1 & 2
from app.models.tenant import Tenant, Role, UserRole
from app.models.user import User, AuthVerificationCode, AuthRateLimit
from app.models.client import Client
from app.models.contract import Contract
from app.models.supplier import Supplier
from app.models.expense import Expense
from app.models.cost_engine import EmployeePayRate, TimesheetCost
from app.models.project_pl import ProjectPLPeriod
from app.models.audit import AuditEvent
from app.models.rbac import PermissionTemplate, UserPermissionOverride, UserProjectAssignment
