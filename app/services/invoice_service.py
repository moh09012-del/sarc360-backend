"""
SARC360 ERP — Invoice Generation Service
توليد الفواتير من بطاقات الوقت المعتمدة
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.timesheet import Timesheet
from app.models.cost_engine import TimesheetCost
from app.models.project import Project
from app.models.contract import Contract
from app.models.employee import Employee
from app.core.config import settings
from app.services.audit import log_event


async def generate_invoice_from_timesheets(
    db: AsyncSession,
    project_id: uuid.UUID,
    tenant_id: uuid.UUID,
    invoice_date: date,
    created_by: uuid.UUID,
    request=None,
) -> Invoice:
    """
    Generate a single invoice from all approved timesheets on a project
    for the month.
    """
    # Get project
    proj_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        raise ValueError("Project not found")

    # Get all approved timesheets for this project (same month as invoice_date)
    month_start = invoice_date.replace(day=1)
    next_month = month_start.replace(month=month_start.month % 12 + 1)
    if month_start.month == 12:
        next_month = next_month.replace(year=next_month.year + 1)

    ts_result = await db.execute(
        select(Timesheet).where(
            Timesheet.tenant_id == tenant_id,
            Timesheet.project_id == project_id,
            Timesheet.status == "approved",
            Timesheet.week_start_date >= month_start,
            Timesheet.week_start_date < next_month,
        )
    )
    timesheets = ts_result.scalars().all()

    if not timesheets:
        raise ValueError("No approved timesheets found for this project/month")

    # Fetch all timesheet costs
    costs_result = await db.execute(
        select(TimesheetCost).where(
            TimesheetCost.tenant_id == tenant_id,
            TimesheetCost.timesheet_id.in_([ts.id for ts in timesheets]),
        )
    )
    costs_map = {tc.timesheet_id: tc for tc in costs_result.scalars()}

    # Calculate totals
    total_cost = sum(
        costs_map[ts.id].cost_amount
        for ts in timesheets
        if ts.id in costs_map
    )

    # Validate against contract value (if PO linked)
    if project.po_id:
        contract_result = await db.execute(
            select(Contract).where(Contract.id == project.po_id)
        )
        contract = contract_result.scalar_one_or_none()
        if contract:
            # Calculate already-invoiced amount
            existing_invoices_result = await db.execute(
                select(func.sum(Invoice.total_sar)).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.po_id == contract.id,
                    Invoice.status != "cancelled",
                )
            )
            existing_total = (
                existing_invoices_result.scalar_one() or Decimal("0.00")
            )

            # Check against contract value
            if existing_total + total_cost > contract.total_value:
                raise ValueError(
                    f"Invoice total (SAR {total_cost}) would exceed contract value "
                    f"(SAR {contract.total_value}). Already invoiced: SAR {existing_total}"
                )

    # Calculate VAT
    vat_amount = total_cost * settings.KSA_VAT_RATE
    invoice_total = total_cost + vat_amount

    # Generate invoice number
    inv_count_result = await db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id)
    )
    inv_count = inv_count_result.scalar_one() + 1
    invoice_number = f"INV-{invoice_date.year}-{inv_count:06d}"

    # Create invoice
    invoice = Invoice(
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        project_id=project_id,
        po_id=project.po_id,
        client_name=project.client_name,
        invoice_date=invoice_date,
        due_date=invoice_date.replace(day=min(invoice_date.day + 30, 28)),
        subtotal_sar=total_cost,
        vat_rate=settings.KSA_VAT_RATE,
        vat_amount_sar=vat_amount,
        total_sar=invoice_total,
        status="draft",
        description=f"Services for {project.name_en} — {month_start.strftime('%B %Y')}",
        created_by=created_by,
    )
    db.add(invoice)
    await db.flush()

    await log_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=created_by,
        action="create",
        entity_type="invoices",
        entity_id=invoice.id,
        details=f"From {len(timesheets)} approved timesheets",
        ip_address=request.client.host if request else None,
    )

    return invoice


async def submit_invoice_to_zatca(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    tenant_id: uuid.UUID,
    submitted_by: uuid.UUID,
    request=None,
) -> Invoice:
    """
    Submit invoice to ZATCA Phase 2 for clearance.
    In production, this would call the FATOORA API.
    For now, it just marks as submitted and auto-approves in sandbox.
    """
    inv_result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id,
        )
    )
    invoice = inv_result.scalar_one_or_none()
    if not invoice:
        raise ValueError("Invoice not found")

    invoice.zatca_status = "submitted"

    # In production, call FATOORA API here
    # For now, auto-approve in sandbox
    if settings.ZATCA_ENV == "sandbox":
        invoice.zatca_status = "approved"
        invoice.zatca_uuid = f"zatca-{invoice.id}"
        invoice.zatca_hash = f"hash-{invoice.id}"

    await db.flush()

    await log_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=submitted_by,
        action="zatca_submit",
        entity_type="invoices",
        entity_id=invoice_id,
        ip_address=request.client.host if request else None,
    )

    return invoice
