"""
SARC360 ERP - Production Seed Script
Seeds: tenant sarc-001, user mohammed@sarc.sa, 3 clients, 3 contracts, 5 projects
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
from sqlalchemy import select, text

# Must import before app modules
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.security import hash_password
from app.models.tenant import Tenant, Role, UserRole
from app.models.user import User
from app.models.client import Client
from app.models.contract import Contract
from app.models.project import Project
import app.models  # noqa - register all models

TENANT_UUID = uuid.UUID("00000001-0000-0000-0000-000000000001")


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── 1) Verify/create tenant ─────────────────────────────────────────
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

        # ── 2) Ensure roles exist ───────────────────────────────────────────
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

        # ── 3) Create user mohammed@sarc.sa ────────────────────────────────
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

            # Assign super_admin role
            res_role = await db.execute(select(Role).where(Role.code == "super_admin"))
            role = res_role.scalar_one_or_none()
            if role:
                db.add(UserRole(tenant_id=TENANT_UUID, user_id=user.id, role_id=role.id))
                print("[+] super_admin role assigned to mohammed@sarc.sa")
        else:
            print("[=] User mohammed@sarc.sa already exists, id:", user.id)

        await db.flush()

        # ── 4) Create 3 clients ────────────────────────────────────────────
        clients_data = [
            ("Saudi Aramco", "أرامكو السعودية", "1010012345", "1234567890"),
            ("Ravago Middle East", None, None, None),
            ("Alfanar", "الفنار", "1010098765", "0987654321"),
        ]

        client_objects = []
        for name_en, name_ar, cr, vat in clients_data:
            res = await db.execute(
                select(Client).where(Client.tenant_id == TENANT_UUID, Client.name_en == name_en)
            )
            client = res.scalar_one_or_none()
            if not client:
                client = Client(
                    tenant_id=TENANT_UUID,
                    name_en=name_en,
                    name_ar=name_ar,
                    cr_number=cr,
                    vat_number=vat,
                    country="SA",
                    is_active=True,
                )
                db.add(client)
                await db.flush()
                print(f"[+] Client '{name_en}' created, id:", client.id)
            else:
                print(f"[=] Client '{name_en}' already exists")
            client_objects.append(client)

        await db.flush()

        # ── 5) Create 3 contracts ───────────────────────────────────────────
        contracts_data = [
            (client_objects[0], "PO-ARAMCO-2026-001", "HSE Site Services", 2500000.00),
            (client_objects[1], "PO-RAVAGO-2026-001", "Electrical Installation Works", 1800000.00),
            (client_objects[2], "PO-ALFANAR-2026-001", "Substation Commissioning", 3200000.00),
        ]

        contract_objects = []
        for client, po_num, title, value in contracts_data:
            res = await db.execute(
                select(Contract).where(
                    Contract.tenant_id == TENANT_UUID,
                    Contract.po_number == po_num,
                )
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
                    start_date="2026-01-01",
                    end_date="2026-12-31",
                    status="active",
                )
                db.add(contract)
                await db.flush()
                print(f"[+] Contract '{po_num}' created, id:", contract.id)
            else:
                print(f"[=] Contract '{po_num}' already exists")
            contract_objects.append(contract)

        await db.flush()

        # ── 6) Create 5 projects ────────────────────────────────────────────
        # Count existing projects for numbering
        count_res = await db.execute(
            select(__import__('sqlalchemy', fromlist=['func']).func.count()).select_from(Project).where(Project.tenant_id == TENANT_UUID)
        )
        existing_count = count_res.scalar_one()

        projects_data = [
            (contract_objects[0], client_objects[0], "HSE Site Services - Phase 1 - Ras Tanura"),
            (contract_objects[0], client_objects[0], "HSE Site Services - Phase 2 - Dhahran"),
            (contract_objects[1], client_objects[1], "Ravago Electrical Installation - Jubail"),
            (contract_objects[2], client_objects[2], "Alfanar Substation - Eastern Province"),
            (contract_objects[2], client_objects[2], "Alfanar Substation Commissioning - Riyadh"),
        ]

        for i, (contract, client, proj_name) in enumerate(projects_data):
            res = await db.execute(
                select(Project).where(
                    Project.tenant_id == TENANT_UUID,
                    Project.name_en == proj_name,
                )
            )
            project = res.scalar_one_or_none()
            if not project:
                proj_num = f"PRJ-{existing_count + i + 1:03d}"
                project = Project(
                    tenant_id=TENANT_UUID,
                    project_number=proj_num,
                    name_en=proj_name,
                    client_name=client.name_en,
                    client_id=client.id,
                    po_id=contract.id,
                    po_number=contract.po_number,
                    start_date="2026-01-01",
                    end_date="2026-12-31",
                    status="active",
                    created_by=user.id,
                )
                db.add(project)
                await db.flush()
                print(f"[+] Project '{proj_num}' created: {proj_name[:50]}")
            else:
                print(f"[=] Project '{proj_name[:50]}' already exists")

        await db.commit()
        print()
        print("[OK] Seed data committed successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
