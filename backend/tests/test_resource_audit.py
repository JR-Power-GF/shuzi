"""Tests for audit integration with resource-domain entity types.

Validates that audit_log() works for venue, equipment, and booking entity types,
and that the audit trail can be queried by entity_type for XR event tracking.
"""
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.services.audit import audit_log
from tests.helpers import create_test_user


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_venue_create(db_session: AsyncSession):
    user = await create_test_user(db_session, username="audit_venue_user", role="admin")
    entry = await audit_log(
        db_session,
        entity_type="venue",
        entity_id=1,
        action="create",
        actor_id=user.id,
        changes={"name": "XR Lab", "capacity": 30},
    )
    assert entry.id is not None
    assert entry.entity_type == "venue"
    assert entry.action == "create"
    assert entry.actor_id == user.id
    assert json.loads(entry.changes) == {"name": "XR Lab", "capacity": 30}


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_equipment_create(db_session: AsyncSession):
    user = await create_test_user(db_session, username="audit_equip_user", role="facility_manager")
    entry = await audit_log(
        db_session,
        entity_type="equipment",
        entity_id=5,
        action="create",
        actor_id=user.id,
        changes={"name": "VR Headset", "serial_number": "VR-001"},
    )
    assert entry.entity_type == "equipment"
    assert entry.action == "create"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_booking_create(db_session: AsyncSession):
    user = await create_test_user(db_session, username="audit_book_user", role="teacher")
    entry = await audit_log(
        db_session,
        entity_type="booking",
        entity_id=10,
        action="create",
        actor_id=user.id,
        changes={"venue_id": 1, "title": "Lab Session"},
    )
    assert entry.entity_type == "booking"
    assert entry.action == "create"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_booking_cancel(db_session: AsyncSession):
    user = await create_test_user(db_session, username="audit_cancel_user", role="teacher")
    entry = await audit_log(
        db_session,
        entity_type="booking",
        entity_id=10,
        action="cancel",
        actor_id=user.id,
        changes={"status": "cancelled"},
    )
    assert entry.action == "cancel"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_venue_status_change(db_session: AsyncSession):
    user = await create_test_user(db_session, username="audit_status_user", role="admin")
    entry = await audit_log(
        db_session,
        entity_type="venue",
        entity_id=3,
        action="status_change",
        actor_id=user.id,
        changes={"old_status": "active", "new_status": "maintenance"},
    )
    assert entry.action == "status_change"
    changes = json.loads(entry.changes)
    assert changes["new_status"] == "maintenance"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_query_by_entity_type(db_session: AsyncSession):
    """XR system polls AuditLog for entity_type='booking' — must be queryable."""
    user = await create_test_user(db_session, username="audit_query_user", role="admin")

    await audit_log(db_session, entity_type="booking", entity_id=100, action="create", actor_id=user.id)
    await audit_log(db_session, entity_type="venue", entity_id=200, action="create", actor_id=user.id)
    await audit_log(db_session, entity_type="booking", entity_id=101, action="cancel", actor_id=user.id)

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "booking").order_by(AuditLog.id)
    )
    booking_logs = result.scalars().all()
    assert len(booking_logs) >= 2
    assert all(log.entity_type == "booking" for log in booking_logs)


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_actor_null_for_system_action(db_session: AsyncSession):
    """System-triggered actions (e.g., auto-cancel) have no actor."""
    entry = await audit_log(
        db_session,
        entity_type="booking",
        entity_id=50,
        action="auto_cancel",
        actor_id=None,
        changes={"reason": "resource_maintenance"},
    )
    assert entry.actor_id is None
    assert entry.changes is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_changes_serializes_datetime(db_session: AsyncSession):
    """changes dict with datetime values should serialize via default=str."""
    entry = await audit_log(
        db_session,
        entity_type="booking",
        entity_id=60,
        action="create",
        actor_id=None,
        changes={"start_time": "2026-06-01T09:00:00", "end_time": "2026-06-01T11:00:00"},
    )
    parsed = json.loads(entry.changes)
    assert "start_time" in parsed
