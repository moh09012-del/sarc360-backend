"""
SARC360 ERP - Realistic Saudi Demo Seed
========================================
Creates a STANDALONE demo tenant (slug: demo-2026-sarc) with realistic
Saudi contracting / manpower-supply data.

ALL data is under one tenant_id — delete the tenant to wipe everything:
    DELETE FROM tenants WHERE slug = 'demo-2026-sarc';

Run:
    cd sarc360-backend
    python scripts/seed_demo.py

Uses ONLY dummy/fictional data — no real persons or companies.
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

# ── Path fix ─────────────────────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
import app.models  # noqa — register all ORM models with Base.metadata

from app.models.tenant import Role, Tenant, UserRole
from app.models.user import User
from app.models.client import Client
from app.models.contract import Contract
from app.models.project import Project
from app.models.employee import Employee
from app.models.supplier import Supplier
from app.models.expense import Expense
from app.models.timesheet import Timesheet
from app.models.invoice import Invoice
from app.models.cost_engine import EmployeePayRate, TimesheetCost
from app.models.project_pl import ProjectPLPeriod

# ── Constants ─────────────────────────────────────────────────────────────────
DEMO_TENANT_SLUG = "demo-2026-sarc"
DEMO_TENANT_ID   = uuid.UUID("dddddddd-0000-0000-0000-000000000001")
SARC_TENANT_ID   = uuid.UUID("00000001-0000-0000-0000-000000000001")  # production tenant


def d(val: str) -> Decimal:
    return Decimal(val)


# ── Main ──────────────────────────────────────────────────────────────────────

async def seed_demo():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        print("\n=== SARC360 Demo Seed ===\n")

        # ── 0. Ensure base roles exist (shared across tenants) ────────────────
        for code, name in [
            ("super_admin", "Super Administrator"),
            ("finance_hr",  "Finance & HR Manager"),
            ("projects",    "Projects Manager"),
            ("employee",    "Employee"),
            ("client",      "Client Portal"),
        ]:
            res = await db.execute(select(Role).where(Role.code == code))
            if not res.scalar_one_or_none():
                db.add(Role(code=code, name=name))
                print(f"  [+] Role '{code}'")
        await db.flush()

        # ── 1. Demo Tenant ───────────────────────────────────────────────────
        res = await db.execute(select(Tenant).where(Tenant.id == DEMO_TENANT_ID))
        tenant = res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=DEMO_TENANT_ID,
                slug=DEMO_TENANT_SLUG,
                legal_name="Demo Company (SARC360 Demo Tenant)",
                city="Al-Khobar",
                country="SA",
                max_users=50,
                is_active=True,
            )
            db.add(tenant)
            await db.flush()
            print(f"  [+] Demo tenant: {DEMO_TENANT_SLUG}")
        else:
            print(f"  [=] Demo tenant already exists — refreshing data")

        # ── 2. Demo Admin User ────────────────────────────────────────────────
        res = await db.execute(
            select(User).where(User.tenant_id == DEMO_TENANT_ID, User.email == "demo@sarc360.local")
        )
        demo_user = res.scalar_one_or_none()
        if not demo_user:
            demo_user = User(
                tenant_id=DEMO_TENANT_ID,
                email="demo@sarc360.local",
                password_hash=hash_password("Demo@12345!"),
                full_name="Demo Admin",
                user_type="staff",
                is_active=True,
                is_email_verified=True,
            )
            db.add(demo_user)
            await db.flush()
            res = await db.execute(select(Role).where(Role.code == "super_admin"))
            role = res.scalar_one_or_none()
            if role:
                db.add(UserRole(tenant_id=DEMO_TENANT_ID, user_id=demo_user.id, role_id=role.id))
            print(f"  [+] Demo user: demo@sarc360.local / Demo@12345!")
        await db.flush()

        # ── 3. Clients ────────────────────────────────────────────────────────
        client_data = [
            dict(
                id=uuid.UUID("cccccccc-0001-0000-0000-000000000001"),
                name_en="Eastern Petrochem Industries Ltd.",
                name_ar="شركة الصناعات البتروكيماوية الشرقية",
                cr_number="2051234567",
                vat_number="310987654310003",
                billing_email="ap@epi-demo.local",
                phone="+9661398765432",
                city="Jubail Industrial City",
                country="SA",
            ),
            dict(
                id=uuid.UUID("cccccccc-0002-0000-0000-000000000001"),
                name_en="Gulf EPC Contractors Co.",
                name_ar="شركة الخليج للمقاولات الهندسية",
                cr_number="2052345678",
                vat_number="310876543210003",
                billing_email="finance@gulf-epc-demo.local",
                phone="+9661313456789",
                city="Al-Khobar",
                country="SA",
            ),
        ]
        clients: dict[uuid.UUID, Client] = {}
        for cd in client_data:
            cid = cd["id"]
            res = await db.execute(select(Client).where(Client.id == cid))
            c = res.scalar_one_or_none()
            if not c:
                c = Client(tenant_id=DEMO_TENANT_ID, **cd)
                db.add(c)
                print(f"  [+] Client: {cd['name_en']}")
            clients[cid] = c
        await db.flush()

        client_epi_id  = uuid.UUID("cccccccc-0001-0000-0000-000000000001")
        client_gepc_id = uuid.UUID("cccccccc-0002-0000-0000-000000000001")

        # ── 4. Contracts / POs ────────────────────────────────────────────────
        contract_data = [
            dict(
                id=uuid.UUID("aaaaaaaa-0001-0000-0000-000000000001"),
                client_id=client_epi_id,
                po_number="EPI-PO-2026-0042",
                title="HSE Manpower Supply — Jubail Complex Q1 2026",
                total_value=d("480000.00"),
                currency="SAR",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 3, 31),
                status="active",
            ),
            dict(
                id=uuid.UUID("aaaaaaaa-0002-0000-0000-000000000001"),
                client_id=client_gepc_id,
                po_number="GEPC-PO-2026-0017",
                title="Mechanical Technicians — Offshore Maintenance Phase 2",
                total_value=d("650000.00"),
                currency="SAR",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 6, 30),
                status="active",
            ),
        ]
        contracts: dict[uuid.UUID, Contract] = {}
        for cd in contract_data:
            cid = cd["id"]
            res = await db.execute(select(Contract).where(Contract.id == cid))
            ct = res.scalar_one_or_none()
            if not ct:
                ct = Contract(tenant_id=DEMO_TENANT_ID, **cd)
                db.add(ct)
                print(f"  [+] Contract: {cd['po_number']} — {cd['total_value']} SAR")
            contracts[cid] = ct
        await db.flush()

        contract_epi_id  = uuid.UUID("aaaaaaaa-0001-0000-0000-000000000001")
        contract_gepc_id = uuid.UUID("aaaaaaaa-0002-0000-0000-000000000001")

        # ── 5. Suppliers ──────────────────────────────────────────────────────
        supplier_data = [
            dict(
                id=uuid.UUID("55555555-0001-0000-0000-000000000001"),
                name="Al-Nakheel Housing Solutions",
                supplier_type="service",
                vat_number="310111222333001",
                email="billing@nakheel-demo.local",
                phone="+9661313887766",
            ),
            dict(
                id=uuid.UUID("55555555-0002-0000-0000-000000000001"),
                name="Saudi Gulf Transport Co.",
                supplier_type="service",
                vat_number="310222333444001",
                email="ops@sgtransport-demo.local",
                phone="+9661313445566",
            ),
            dict(
                id=uuid.UUID("55555555-0003-0000-0000-000000000001"),
                name="Al-Jazira Safety Equipment",
                supplier_type="materials",
                vat_number="310333444555001",
                email="sales@jazira-safety-demo.local",
                phone="+9661313223344",
            ),
        ]
        suppliers: dict[uuid.UUID, Supplier] = {}
        for sd in supplier_data:
            sid = sd["id"]
            res = await db.execute(select(Supplier).where(Supplier.id == sid))
            s = res.scalar_one_or_none()
            if not s:
                s = Supplier(tenant_id=DEMO_TENANT_ID, **sd)
                db.add(s)
                print(f"  [+] Supplier: {sd['name']}")
            suppliers[sid] = s
        await db.flush()

        sup_housing_id   = uuid.UUID("55555555-0001-0000-0000-000000000001")
        sup_transport_id = uuid.UUID("55555555-0002-0000-0000-000000000001")
        sup_safety_id    = uuid.UUID("55555555-0003-0000-0000-000000000001")

        # ── 6. Projects ───────────────────────────────────────────────────────
        project_data = [
            dict(
                id=uuid.UUID("bbbbbbbb-0001-0000-0000-000000000001"),
                project_number="PRJ-D-001",
                name_en="EPI Jubail — HSE Manpower Supply (March 2026)",
                name_ar="توريد عمالة السلامة — الجبيل (مارس 2026)",
                client_name="Eastern Petrochem Industries Ltd.",
                client_id=client_epi_id,
                po_id=contract_epi_id,
                po_number="EPI-PO-2026-0042",
                po_value_sar=d("480000.00"),
                contract_value_sar=d("480000.00"),
                start_date=date(2026, 1, 1),
                end_date=date(2026, 3, 31),
                department="hse",
                location="Jubail Industrial City, Eastern Province",
                description="Supply of 6 HSE officers and 2 Safety Supervisors for Q1 2026 shutdown.",
                status="active",
            ),
            dict(
                id=uuid.UUID("bbbbbbbb-0002-0000-0000-000000000001"),
                project_number="PRJ-D-002",
                name_en="GEPC Offshore — Mechanical Technicians (Feb-Mar 2026)",
                name_ar="فنيو ميكانيكا بحري — الخليج للمقاولات",
                client_name="Gulf EPC Contractors Co.",
                client_id=client_gepc_id,
                po_id=contract_gepc_id,
                po_number="GEPC-PO-2026-0017",
                po_value_sar=d("650000.00"),
                contract_value_sar=d("650000.00"),
                start_date=date(2026, 2, 1),
                end_date=date(2026, 6, 30),
                department="operations",
                location="Ras Al-Khair, Eastern Province",
                description="Provision of 4 mechanical technicians for offshore maintenance phase 2.",
                status="active",
            ),
        ]
        projects: dict[uuid.UUID, Project] = {}
        for pd in project_data:
            pid = pd["id"]
            res = await db.execute(select(Project).where(Project.id == pid))
            p = res.scalar_one_or_none()
            if not p:
                p = Project(tenant_id=DEMO_TENANT_ID, **pd)
                db.add(p)
                print(f"  [+] Project: {pd['project_number']} — {pd['name_en']}")
            projects[pid] = p
        await db.flush()

        prj_epi_id  = uuid.UUID("bbbbbbbb-0001-0000-0000-000000000001")
        prj_gepc_id = uuid.UUID("bbbbbbbb-0002-0000-0000-000000000001")

        # ── 7. Employees ──────────────────────────────────────────────────────
        #
        # Mix: Saudi nationals + expats (common in KSA contracting)
        #
        employee_data = [
            # HSE Officers (Project 1)
            dict(id=uuid.UUID("eeeeeeee-0001-0000-0000-000000000001"),
                 employee_number="EMP-D-001", full_name_en="Ahmed Khalid Al-Otaibi",
                 full_name_ar="أحمد خالد العتيبي", nationality="Saudi",
                 iqama_number="1012345678", job_title="HSE Supervisor",
                 department="hse", hire_date=date(2023, 3, 1),
                 basic_salary_sar=d("9500.00"), housing_allowance_sar=d("2500.00"),
                 transport_allowance_sar=d("800.00"), employment_type="internal"),
            dict(id=uuid.UUID("eeeeeeee-0002-0000-0000-000000000001"),
                 employee_number="EMP-D-002", full_name_en="Ramesh Kumar Pillai",
                 full_name_ar="راميش كومار", nationality="Indian",
                 iqama_number="2087654321", job_title="HSE Officer",
                 department="hse", hire_date=date(2022, 7, 15),
                 basic_salary_sar=d("6500.00"), housing_allowance_sar=d("1500.00"),
                 transport_allowance_sar=d("500.00"), employment_type="internal"),
            dict(id=uuid.UUID("eeeeeeee-0003-0000-0000-000000000001"),
                 employee_number="EMP-D-003", full_name_en="Mohammed Yusuf Al-Qahtani",
                 full_name_ar="محمد يوسف القحطاني", nationality="Saudi",
                 iqama_number="1034567890", job_title="HSE Officer",
                 department="hse", hire_date=date(2024, 1, 10),
                 basic_salary_sar=d("7800.00"), housing_allowance_sar=d("2000.00"),
                 transport_allowance_sar=d("600.00"), employment_type="internal"),
            # Safety Supervisors (Project 1)
            dict(id=uuid.UUID("eeeeeeee-0004-0000-0000-000000000001"),
                 employee_number="EMP-D-004", full_name_en="Suresh Babu Nair",
                 full_name_ar="سوريش بابو", nationality="Indian",
                 iqama_number="2076543210", job_title="Safety Supervisor",
                 department="hse", hire_date=date(2021, 5, 20),
                 basic_salary_sar=d("8200.00"), housing_allowance_sar=d("2000.00"),
                 transport_allowance_sar=d("600.00"), employment_type="internal"),
            dict(id=uuid.UUID("eeeeeeee-0005-0000-0000-000000000001"),
                 employee_number="EMP-D-005", full_name_en="Abdullah Saeed Al-Ghamdi",
                 full_name_ar="عبدالله سعيد الغامدي", nationality="Saudi",
                 iqama_number="1056789012", job_title="Safety Supervisor",
                 department="hse", hire_date=date(2023, 8, 1),
                 basic_salary_sar=d("8500.00"), housing_allowance_sar=d("2200.00"),
                 transport_allowance_sar=d("700.00"), employment_type="internal"),
            # Mechanical Technicians (Project 2)
            dict(id=uuid.UUID("eeeeeeee-0006-0000-0000-000000000001"),
                 employee_number="EMP-D-006", full_name_en="Arjun Singh Mehta",
                 full_name_ar="أرجون سينغ", nationality="Indian",
                 iqama_number="2065432109", job_title="Mechanical Technician",
                 department="operations", hire_date=date(2022, 11, 1),
                 basic_salary_sar=d("5800.00"), housing_allowance_sar=d("1200.00"),
                 transport_allowance_sar=d("400.00"), employment_type="internal"),
            dict(id=uuid.UUID("eeeeeeee-0007-0000-0000-000000000001"),
                 employee_number="EMP-D-007", full_name_en="Tariq Hamad Al-Zahrani",
                 full_name_ar="طارق حمد الزهراني", nationality="Saudi",
                 iqama_number="1078901234", job_title="Mechanical Technician",
                 department="operations", hire_date=date(2023, 6, 15),
                 basic_salary_sar=d("6200.00"), housing_allowance_sar=d("1600.00"),
                 transport_allowance_sar=d("500.00"), employment_type="internal"),
            dict(id=uuid.UUID("eeeeeeee-0008-0000-0000-000000000001"),
                 employee_number="EMP-D-008", full_name_en="Vijay Rajan Pillai",
                 full_name_ar="فيجاي راجان", nationality="Indian",
                 iqama_number="2054321098", job_title="Mechanical Technician Sr.",
                 department="operations", hire_date=date(2020, 3, 10),
                 basic_salary_sar=d("7000.00"), housing_allowance_sar=d("1800.00"),
                 transport_allowance_sar=d("500.00"), employment_type="internal"),
        ]
        emp_ids = []
        for ed in employee_data:
            eid = ed.pop("id")
            res = await db.execute(select(Employee).where(Employee.id == eid))
            emp = res.scalar_one_or_none()
            if not emp:
                emp = Employee(id=eid, tenant_id=DEMO_TENANT_ID, status="active",
                               gosi_enrolled=True, **ed)
                db.add(emp)
                print(f"  [+] Employee: {ed['employee_number']} — {ed['full_name_en']}")
            emp_ids.append(eid)
        await db.flush()
        print(f"  >> {len(emp_ids)} employees ready")

        emp_d = {f"EMP-D-{i:03d}": emp_ids[i-1] for i in range(1, 9)}

        # ── 8. Pay Rates ─────────────────────────────────────────────────────
        # hourly_cost = (basic + housing + transport) * (1 + 0.10 GOSI) / 240
        pay_rates_data = [
            # emp_id, monthly_gross, employer_cost_rate
            (emp_d["EMP-D-001"], d("12800.00"), d("0.10")),
            (emp_d["EMP-D-002"], d("8500.00"),  d("0.00")),  # expat — no GOSI employer
            (emp_d["EMP-D-003"], d("10400.00"), d("0.10")),
            (emp_d["EMP-D-004"], d("10800.00"), d("0.00")),
            (emp_d["EMP-D-005"], d("11400.00"), d("0.10")),
            (emp_d["EMP-D-006"], d("7400.00"),  d("0.00")),
            (emp_d["EMP-D-007"], d("8300.00"),  d("0.10")),
            (emp_d["EMP-D-008"], d("9300.00"),  d("0.00")),
        ]
        rate_map: dict[uuid.UUID, EmployeePayRate] = {}
        for emp_id, gross, gosi in pay_rates_data:
            res = await db.execute(
                select(EmployeePayRate).where(
                    EmployeePayRate.tenant_id == DEMO_TENANT_ID,
                    EmployeePayRate.employee_id == emp_id,
                    EmployeePayRate.effective_to.is_(None),
                )
            )
            rate = res.scalar_one_or_none()
            if not rate:
                rate = EmployeePayRate(
                    tenant_id=DEMO_TENANT_ID,
                    employee_id=emp_id,
                    effective_from=date(2026, 1, 1),
                    effective_to=None,
                    monthly_gross_salary=gross,
                    employer_cost_rate=gosi,
                    standard_monthly_hours=d("240.00"),
                )
                rate.compute_hourly_cost()
                db.add(rate)
                await db.flush()
                await db.refresh(rate)
            rate_map[emp_id] = rate
        print(f"  [+] Pay rates for {len(rate_map)} employees")
        await db.flush()

        # ── 9. Timesheets (March 2026 — 26 working days) ──────────────────────
        #
        # Week start dates in March 2026 (Mon):
        #   Week 1: Mar 2 (Mon)
        #   Week 2: Mar 9
        #   Week 3: Mar 16
        #   Week 4: Mar 23
        # The week structure:
        #   sun/mon/tue/wed/thu = 8h workdays
        #   fri = off (Friday = weekly off in KSA)
        #   sat = 8h (some contracts run Sat)
        #
        # Project 1 employees: EMP-D-001..005
        # Project 2 employees: EMP-D-006..008

        def ts_number(n: int) -> str:
            return f"TS-D-{n:04d}"

        ts_counter = 1

        # 4 weeks, 5 employees for project 1, 3 for project 2 = 32 timesheets total
        week_starts = [date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16), date(2026, 3, 23)]

        project1_emps = [emp_d[f"EMP-D-{i:03d}"] for i in range(1, 6)]
        project2_emps = [emp_d[f"EMP-D-{i:03d}"] for i in range(6, 9)]

        approved_ts_ids = []   # for cost calculation
        invoiceable_ts_ids = []

        for week_start in week_starts:
            for emp_id in project1_emps + project2_emps:
                proj_id = prj_epi_id if emp_id in project1_emps else prj_gepc_id
                res = await db.execute(
                    select(Timesheet).where(
                        Timesheet.tenant_id == DEMO_TENANT_ID,
                        Timesheet.employee_id == emp_id,
                        Timesheet.project_id == proj_id,
                        Timesheet.week_start_date == week_start,
                    )
                )
                ts = res.scalar_one_or_none()
                if not ts:
                    ts = Timesheet(
                        tenant_id=DEMO_TENANT_ID,
                        employee_id=emp_id,
                        project_id=proj_id,
                        timesheet_number=ts_number(ts_counter),
                        week_start_date=week_start,
                        hours_sun=d("8.00"),
                        hours_mon=d("8.00"),
                        hours_tue=d("8.00"),
                        hours_wed=d("8.00"),
                        hours_thu=d("8.00"),
                        hours_fri=d("0.00"),  # Friday off
                        hours_sat=d("8.00"),  # Saturday working
                        status="approved",
                        submitted_at=datetime(2026, week_start.month, week_start.day + 6,
                                              17, 0, 0, tzinfo=timezone.utc),
                        approved_at=datetime(2026, week_start.month, min(week_start.day + 7, 31),
                                             9, 0, 0, tzinfo=timezone.utc),
                        approved_by=demo_user.id,
                        notes=f"Week of {week_start} — all days on site",
                    )
                    db.add(ts)
                    await db.flush()
                    await db.refresh(ts)
                    ts_counter += 1

                if ts.status == "approved":
                    approved_ts_ids.append((ts.id, emp_id, proj_id))
                    if proj_id == prj_epi_id:
                        invoiceable_ts_ids.append(ts.id)
        await db.flush()
        print(f"  [+] {ts_counter - 1} timesheets (approved, March 2026)")

        # ── 10. Timesheet Costs ──────────────────────────────────────────────
        for ts_id, emp_id, proj_id in approved_ts_ids:
            res = await db.execute(
                select(TimesheetCost).where(
                    TimesheetCost.tenant_id == DEMO_TENANT_ID,
                    TimesheetCost.timesheet_id == ts_id,
                )
            )
            if res.scalar_one_or_none():
                continue
            rate = rate_map.get(emp_id)
            if not rate:
                continue
            hours = d("48.00")  # 6 days × 8 hours
            hourly = (rate.monthly_gross_salary * (1 + rate.employer_cost_rate)) / d("240.00")
            hourly = hourly.quantize(Decimal("0.000001"))
            cost_amt = (hours * hourly).quantize(Decimal("0.01"))
            tc = TimesheetCost(
                tenant_id=DEMO_TENANT_ID,
                timesheet_id=ts_id,
                employee_rate_id=rate.id,
                hours=hours,
                hourly_cost=hourly,
                cost_amount=cost_amt,
                costed_by=demo_user.id,
            )
            db.add(tc)
        await db.flush()
        print(f"  [+] Timesheet costs computed for all approved timesheets")

        # ── 11. Expenses ─────────────────────────────────────────────────────
        expense_data = [
            # Project 1 (EPI)
            dict(
                project_id=prj_epi_id, supplier_id=sup_housing_id,
                po_id=contract_epi_id,
                expense_date=date(2026, 3, 1),
                category="subcontractor",
                description="Staff accommodation — Jubail, March 2026 (7 rooms × 30 days)",
                amount_net=d("21000.00"), vat_amount=d("3150.00"),
                status="posted",
            ),
            dict(
                project_id=prj_epi_id, supplier_id=sup_transport_id,
                po_id=contract_epi_id,
                expense_date=date(2026, 3, 1),
                category="transport",
                description="Bus hire — daily Khobar-Jubail transport, March 2026",
                amount_net=d("8500.00"), vat_amount=d("1275.00"),
                status="posted",
            ),
            dict(
                project_id=prj_epi_id, supplier_id=sup_safety_id,
                po_id=None,
                expense_date=date(2026, 3, 5),
                category="materials",
                description="PPE consumables — safety helmets, gloves, harnesses",
                amount_net=d("4200.00"), vat_amount=d("630.00"),
                status="approved",
            ),
            # Project 2 (GEPC)
            dict(
                project_id=prj_gepc_id, supplier_id=sup_housing_id,
                po_id=contract_gepc_id,
                expense_date=date(2026, 3, 1),
                category="subcontractor",
                description="Offshore accommodation — Ras Al-Khair camp, March 2026",
                amount_net=d("12000.00"), vat_amount=d("1800.00"),
                status="posted",
            ),
            dict(
                project_id=prj_gepc_id, supplier_id=sup_transport_id,
                po_id=None,
                expense_date=date(2026, 3, 2),
                category="transport",
                description="Vehicle hire for technicians — site mobilization",
                amount_net=d("3600.00"), vat_amount=d("540.00"),
                status="approved",
            ),
        ]
        exp_count = 0
        for ed in expense_data:
            res = await db.execute(
                select(Expense).where(
                    Expense.tenant_id == DEMO_TENANT_ID,
                    Expense.project_id == ed["project_id"],
                    Expense.expense_date == ed["expense_date"],
                    Expense.category == ed["category"],
                    Expense.description == ed["description"],
                )
            )
            if not res.scalar_one_or_none():
                gl_posted_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc) if ed["status"] == "posted" else None
                exp = Expense(
                    tenant_id=DEMO_TENANT_ID,
                    amount_gross=ed["amount_net"] + ed["vat_amount"],
                    gl_posted_at=gl_posted_at,
                    created_by=demo_user.id,
                    **ed,
                )
                db.add(exp)
                exp_count += 1
        await db.flush()
        print(f"  [+] {exp_count} expenses (accommodation, transport, materials)")

        # ── 12. Invoices ─────────────────────────────────────────────────────
        # Invoice 1: Project EPI March — PAID
        # Invoice 2: Project GEPC March — GL POSTED (sent/outstanding)

        invoice_data = [
            dict(
                id=uuid.UUID("ffffffff-0001-0000-0000-000000000001"),
                invoice_number="INV-D-2026-0001",
                tenant_id=DEMO_TENANT_ID,
                project_id=prj_epi_id,
                po_id=contract_epi_id,
                client_name="Eastern Petrochem Industries Ltd.",
                invoice_date=date(2026, 3, 31),
                due_date=date(2026, 4, 30),
                subtotal_sar=d("155000.00"),
                vat_rate=d("0.1500"),
                vat_amount_sar=d("23250.00"),
                total_sar=d("178250.00"),
                description="HSE Manpower Supply Services — March 2026 (EPI-PO-2026-0042)",
                status="paid",
                payment_date=date(2026, 4, 15),
                payment_reference="TRF-SNB-2026-0412",
                gl_posted=True,
                gl_posted_at=datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc),
                gl_entry_ref="GL-INV-D-2026-0001",
                zatca_status="approved",
                created_by=demo_user.id,
            ),
            dict(
                id=uuid.UUID("ffffffff-0002-0000-0000-000000000001"),
                invoice_number="INV-D-2026-0002",
                tenant_id=DEMO_TENANT_ID,
                project_id=prj_gepc_id,
                po_id=contract_gepc_id,
                client_name="Gulf EPC Contractors Co.",
                invoice_date=date(2026, 3, 31),
                due_date=date(2026, 4, 30),
                subtotal_sar=d("96000.00"),
                vat_rate=d("0.1500"),
                vat_amount_sar=d("14400.00"),
                total_sar=d("110400.00"),
                description="Mechanical Technicians — March 2026 (GEPC-PO-2026-0017)",
                status="sent",
                gl_posted=True,
                gl_posted_at=datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
                gl_entry_ref="GL-INV-D-2026-0002",
                zatca_status="submitted",
                created_by=demo_user.id,
            ),
        ]
        inv_count = 0
        for inv_d in invoice_data:
            iid = inv_d.pop("id")
            res = await db.execute(select(Invoice).where(Invoice.id == iid))
            if not res.scalar_one_or_none():
                inv = Invoice(id=iid, **inv_d)
                db.add(inv)
                inv_count += 1
        await db.flush()
        print(f"  [+] {inv_count} invoices (1 paid, 1 outstanding)")

        # ── 13. Project P&L Periods ───────────────────────────────────────────
        # Compute realistic P&L from the data above

        pl_data = [
            dict(
                project_id=prj_epi_id,
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 31),
                revenue_net=d("155000.00"),      # invoice subtotal
                labor_cost=d("97920.00"),         # 5 employees × 4 weeks × 48h × avg rate
                vendor_cost=d("33700.00"),         # accommodation + transport + PPE
                overhead_allocated=d("7750.00"),   # 5% overhead allocation
                billable_hours=d("960.00"),        # 5 emp × 4 weeks × 48h
                total_hours=d("960.00"),
                computed_by=demo_user.id,
            ),
            dict(
                project_id=prj_gepc_id,
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 31),
                revenue_net=d("96000.00"),
                labor_cost=d("55440.00"),         # 3 employees × 4 weeks × 48h × avg rate
                vendor_cost=d("17940.00"),         # accommodation + transport
                overhead_allocated=d("4800.00"),
                billable_hours=d("576.00"),        # 3 emp × 4 weeks × 48h
                total_hours=d("576.00"),
                computed_by=demo_user.id,
            ),
        ]
        for pd in pl_data:
            res = await db.execute(
                select(ProjectPLPeriod).where(
                    ProjectPLPeriod.tenant_id == DEMO_TENANT_ID,
                    ProjectPLPeriod.project_id == pd["project_id"],
                    ProjectPLPeriod.period_start == pd["period_start"],
                    ProjectPLPeriod.period_end == pd["period_end"],
                )
            )
            if not res.scalar_one_or_none():
                pl = ProjectPLPeriod(tenant_id=DEMO_TENANT_ID, **pd)
                pl.recompute()   # compute gross_profit, net_profit, utilization_rate
                db.add(pl)
        await db.flush()
        print(f"  [+] P&L periods for both projects (March 2026)")

        # ── Commit ────────────────────────────────────────────────────────────
        await db.commit()

        print("""
=== Demo Seed Complete ===

Login credentials:
  Tenant ID : dddddddd-0000-0000-0000-000000000001
  Email     : demo@sarc360.local
  Password  : Demo@12345!

Delete all demo data:
  DELETE FROM tenants WHERE slug = 'demo-2026-sarc';

Dashboard query:
  GET /api/v1/dashboard?start=2026-03-01&end=2026-03-31
  (should show ~SAR 251,000 revenue, ~SAR 153,360 labor+vendor costs)
""")


if __name__ == "__main__":
    asyncio.run(seed_demo())
