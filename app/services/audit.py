"""
SARC360 ERP - Audit Helper
تسجيل أحداث التدقيق
"""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


async def log_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert an audit event row (fire-and-forget within same transaction)."""
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=before_data,
        after_data=after_data,
        request_id=request_id,
        ip_address=ip_address,
    )
    db.add(event)
