"""
SARC360 ERP - Full Seed Script
Implements Task 1 requirements from user request.
"""
import asyncio
import uuid
import sys
from datetime import date

# Ensure stdout uses UTF-8 on Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Must import before app modules
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.security import hash_password
from app.models.tenant import Tenant, Role, UserRole
from app.models.user import User
from app.models.client import Client
from app.models.contract import Contract
from app.models.project import Project
from app.models.employee import Employee
from app.models.cost_engine import EmployeePayRate, TimesheetCost
from app.models.timesheet import Timesheet
import app.models  # noqa - register all models

TENANT_UUID = uuid.UUID("00000001-0000-0000-0000-000000000001")


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Tenant
        res = await db.execute(select(Tenant).where(Tenant.id == TENANT_UUID))
        tenant = res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=TENANT_UUID,
                slug="sarc-001",
                legal_name="Sama Al-Rawabi Contracting Co.",
                city="Al-Khobar",
                country="SA",
                max_users=100,
                is_active=True,
            )
            db.add(tenant)
            await db.flush()
            print("[+] Tenant sarc-001 created")
        else:
            print("[=] Tenant sarc-001 already exists")

        # Roles
        roles_needed = [
            ("super_admin", "Super Administrator"),
            ("finance_hr", "Finance & HR Manager"),
            ("projects", "Projects Manager"),
            ("employee", "Employee"),
            ("client", "Client Portal"),
        ]
        for code, name in roles_needed:
            res = await db.execute(select(Role).where(Role.code == code))
            if not res.scalar_one_or_none():
                db.add(Role(code=code, name=name))
                print(f"[+] Role '{code}' created")

        await db.flush()

        # Super admin user
        res = await db.execute(
            select(User).where(User.tenant_id == TENANT_UUID, User.email == "mohammed@sarc.sa")
        )
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                tenant_id=TENANT_UUID,
                email="mohammed@sarc.sa",
                password_hash=hash_password("Sarc@2025!"),
                full_name="Mohammed Al-Amri",
                user_type="staff",
                is_active=True,
            )
            db.add(user)
            await db.flush()
            print("[+] User mohammed@sarc.sa created, id:", user.id)

            role = (await db.execute(select(Role).where(Role.code == "super_admin"))).scalar_one_or_none()
            if role:
                db.add(UserRole(tenant_id=TENANT_UUID, user_id=user.id, role_id=role.id))
                print("[+] super_admin role assigned to mohammed@sarc.sa")
        else:
            print("[=] User mohammed@sarc.sa already exists, id:", user.id)

        await db.flush()

        # Clients
        clients_data = [
            ("Saudi Aramco", "أرامكو السعودية", "310081084900003"),
            ("Ravago Middle East", "رافاغو الشرق الأوسط", None),
            ("alfanar", "الفنار", "300075588900003"),
        ]
        client_objects = []
        for name_en, name_ar, vat in clients_data:
            res = await db.execute(
                select(Client).where(Client.tenant_id == TENANT_UUID, Client.name_en == name_en)
            )
            client = res.scalar_one_or_none()
            if not client:
                client = Client(
                    tenant_id=TENANT_UUID,
                    name_en=name_en,
                    name_ar=name_ar,
                    country="SA",
                    vat_number=vat,
                    is_active=True,
                )
                db.add(client)
                await db.flush()
                print(f"[+] Client '{name_en}' created, id:", client.id)
            else:
                print(f"[=] Client '{name_en}' already exists")
            client_objects.append(client)

        await db.flush()

        # Contracts
        contracts_data = [
            (client_objects[0], "PO-ARAMCO-2026-001", "HSE Services", 5000000.00),
            (client_objects[1], "PO-RAVAGO-2026-001", "Operations Support", 2500000.00),
            (client_objects[2], "PO-ALFANAR-2026-001", "Manpower Services", 3500000.00),
        ]
        contract_objects = []
        for client, po_num, title, value in contracts_data:
            res = await db.execute(
                select(Contract).where(Contract.tenant_id == TENANT_UUID, Contract.po_number == po_num)
            )
            contract = res.scalar_one_or_none()
            if not contract:
                contract = Contract(
                    tenant_id=TENANT_UUID,
                    client_id=client.id,
                    po_number=po_num,
                    title=title,
                    currency="SAR",
                    total_value=value,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    status="active",
                )
                db.add(contract)
                await db.flush()
                print(f"[+] Contract '{po_num}' created, id:", contract.id)
            else:
                print(f"[=] Contract '{po_num}' already exists")
            contract_objects.append(contract)

        await db.flush()

        # Projects
        projects_data = [
            ("PRJ-2026-001", "Aramco Ras Tanura HSE", client_objects[0], contract_objects[0]),
            ("PRJ-2026-002", "Aramco Dhahran Security", client_objects[0], contract_objects[0]),
            ("PRJ-2026-003", "Ravago Jubail Operations", client_objects[1], contract_objects[1]),
            ("PRJ-2026-004", "alfanar Eastern Province", client_objects[2], contract_objects[2]),
            ("PRJ-2026-005", "alfanar Riyadh Manpower", client_objects[2], contract_objects[2]),
        ]
        project_objects = []
        for proj_num, proj_name, client, contract in projects_data:
            res = await db.execute(
                select(Project).where(Project.tenant_id == TENANT_UUID, Project.project_number == proj_num)
            )
            project = res.scalar_one_or_none()
            if not project:
                project = Project(
                    tenant_id=TENANT_UUID,
                    project_number=proj_num,
                    name_en=proj_name,
                    name_ar=None,
                    client_name=client.name_en,
                    client_id=client.id,
                    po_id=contract.id,
                    po_number=contract.po_number,
                    po_value_sar=contract.total_value,
                    contract_value_sar=contract.total_value,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    status="active",
                    created_by=user.id,
                )
                db.add(project)
                await db.flush()
                print(f"[+] Project '{proj_num}' created, id:", project.id)
            else:
                print(f"[=] Project '{proj_num}' already exists")
            project_objects.append(project)

        await db.flush()

        # Employees
        employees_data = [
            ("EMP-001", "Ahmed Al-Zahrani", "", "HSE Supervisor", "Saudi", 12000),
            ("EMP-002", "Mohammed Al-Ghamdi", "", "Site Engineer", "Saudi", 14000),
            ("EMP-003", "Sudheer Rahim", "", "Operations Manager", "Indian", 18000),
            ("EMP-004", "Tariq Al-Dossari", "", "Project Coordinator", "Saudi", 10000),
            ("EMP-005", "Rajesh Kumar", "", "Mechanical Technician", "Indian", 8000),
            ("EMP-006", "Faris Al-Mutairi", "", "Safety Officer", "Saudi", 11000),
            ("EMP-007", "Ali Al-Qarni", "", "Electrician", "Yemeni", 7500),
            ("EMP-008", "Bilal Siddiqui", "", "Civil Technician", "Pakistani", 7000),
            ("EMP-009", "Saeed Al-Anazi", "", "Logistics Coordinator", "Saudi", 9000),
            ("EMP-010", "Nasser Al-Mutairi", "", "Document Controller", "Saudi", 7800),
            ("EMP-011", "Ayman Al-Harbi", "", "Quality Inspector", "Saudi", 8500),
            ("EMP-012", "Ahmed Al-Jaber", "", "Surveyor", "Sudanese", 7700),
            ("EMP-013", "Ravi Kumar", "", "Welding Technician", "Indian", 8200),
            ("EMP-014", "Mohamed Othman", "", "Equipment Operator", "Egyptian", 7600),
            ("EMP-015", "Khalid Al-Nasser", "", "Site Planner", "Saudi", 13000),
            ("EMP-016", "Hassan Al-Fahad", "", "Safety Engineer", "Saudi", 14500),
            ("EMP-017", "Sultan Al-Rasheed", "", "Procurement Specialist", "Saudi", 9800),
            ("EMP-018", "Jamal Al-Amiri", "", "Admin Assistant", "Sudanese", 6200),
            ("EMP-019", "Omar Al-Shammari", "", "Electrical Supervisor", "Saudi", 12500),
            ("EMP-020", "Yusef Al-Faraj", "", "Mechanical Supervisor", "Saudi", 12800),
            ("EMP-021", "Riyad Al-Saeed", "", "Marshal", "Egyptian", 7200),
            ("EMP-022", "Fahad Al-Khaldi", "", "IT Support", "Saudi", 8800),
        ]

        employee_objects = []
        for emp_num, name, name_ar, title, nationality, salary in employees_data:
            res = await db.execute(
                select(Employee).where(Employee.tenant_id == TENANT_UUID, Employee.employee_number == emp_num)
            )
            emp = res.scalar_one_or_none()
            if not emp:
                emp = Employee(
                    tenant_id=TENANT_UUID,
                    employee_number=emp_num,
                    full_name_en=name,
                    full_name_ar=name_ar or None,
                    nationality=nationality,
                    job_title=title,
                    employment_type="internal",
                    hire_date=date(2026, 1, 1),
                    basic_salary_sar=salary,
                    housing_allowance_sar=0,
                    transport_allowance_sar=0,
                    other_allowances_sar=0,
                    status="active",
                    created_by=user.id,
                )
                db.add(emp)
                await db.flush()
                print(f"[+] Employee '{name}' created, id:", emp.id)
            else:
                print(f"[=] Employee '{name}' already exists")
            employee_objects.append((emp, salary))

        await db.flush()

        # Pay rates
        pay_rate_objects = []
        for emp, salary in employee_objects:
            res = await db.execute(
                select(EmployeePayRate).where(
                    EmployeePayRate.tenant_id == TENANT_UUID,
                    EmployeePayRate.employee_id == emp.id,
                    EmployeePayRate.effective_from == date(2026, 3, 1),
                )
            )
            pr = res.scalar_one_or_none()
            if not pr:
                pr = EmployeePayRate(
                    tenant_id=TENANT_UUID,
                    employee_id=emp.id,
                    effective_from=date(2026, 3, 1),
                    effective_to=None,
                    monthly_gross_salary=salary,
                    employer_cost_rate=0.12,
                    standard_monthly_hours=240,
                    hourly_cost=0,
                )
                pr.compute_hourly_cost()
                db.add(pr)
                await db.flush()
                print(f"[+] Pay rate for {emp.full_name_en} created, hourly_cost={pr.hourly_cost}")
            else:
                print(f"[=] Pay rate for {emp.full_name_en} already exists")
            pay_rate_objects.append(pr)

        await db.flush()

        # Timesheets March 2026 (22 working days)
        week_start_dates = [
            date(2026, 3, 2),
            date(2026, 3, 9),
            date(2026, 3, 16),
            date(2026, 3, 23),
            date(2026, 3, 30),
        ]

        # Assign one project per employee by business rule for simplicity.
        employee_project_map = {
            "EMP-001": project_objects[0].id,
            "EMP-002": project_objects[1].id,
            "EMP-003": project_objects[2].id,
            "EMP-004": project_objects[4].id,
            "EMP-005": project_objects[2].id,
            "EMP-006": project_objects[0].id,
            "EMP-007": project_objects[3].id,
            "EMP-008": project_objects[2].id,
        }

        for emp, _ in employee_objects:
            for i, ws in enumerate(week_start_dates, start=1):
                ts_num = f"TS-2026-{emp.employee_number}-{i:02d}"
                # Avoid duplicates
                res = await db.execute(
                    select(Timesheet).where(Timesheet.tenant_id == TENANT_UUID, Timesheet.timesheet_number == ts_num)
                )
                ts = res.scalar_one_or_none()
                if ts:
                    continue

                if i < 5:
                    hours = dict(hours_sun=0, hours_mon=8, hours_tue=8, hours_wed=8, hours_thu=8, hours_fri=8, hours_sat=0)
                else:
                    # Week 5: Mar 30-31 only
                    hours = dict(hours_sun=0, hours_mon=8, hours_tue=8, hours_wed=0, hours_thu=0, hours_fri=0, hours_sat=0)

                project_id = employee_project_map.get(emp.employee_number, project_objects[0].id)

                ts = Timesheet(
                    tenant_id=TENANT_UUID,
                    timesheet_number=ts_num,
                    employee_id=emp.id,
                    project_id=project_id,
                    week_start_date=ws,
                    status='draft',
                    created_by=user.id,
                    **hours,
                )
                db.add(ts)

        await db.flush()

        await db.commit()
        print("\n[OK] Full seed data committed successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
