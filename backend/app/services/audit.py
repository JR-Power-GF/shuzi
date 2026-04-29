"""Audit logging service."""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def audit_log(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor_id: int | None = None,
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an audit log entry within the current transaction."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        changes=json.dumps(changes, default=str) if changes else None,
    )
    db.add(entry)
    await db.flush()
    return entry
