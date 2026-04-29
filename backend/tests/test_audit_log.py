import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from tests.helpers import create_test_user


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_model_basic(db_session: AsyncSession):
    user = await create_test_user(db_session, username="audit_tester", role="admin")
    entry = AuditLog(
        entity_type="test_entity",
        entity_id=1,
        action="create",
        actor_id=user.id,
        changes=json.dumps({"name": "test"}),
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    log = result.scalar_one()
    assert log.entity_type == "test_entity"
    assert log.action == "create"
    assert log.actor_id == user.id
    assert json.loads(log.changes) == {"name": "test"}


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_changes_none(db_session: AsyncSession):
    entry = AuditLog(
        entity_type="test_entity",
        entity_id=2,
        action="delete",
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    log = result.scalar_one()
    assert log.changes is None
    assert log.actor_id is None


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_service(db_session: AsyncSession):
    from app.services.audit import audit_log

    user = await create_test_user(db_session, username="audit_svc_user", role="admin")
    entry = await audit_log(
        db_session,
        entity_type="reservation",
        entity_id=42,
        action="create",
        actor_id=user.id,
        changes={"venue_id": 1, "start": "2026-06-01T10:00:00"},
    )

    assert entry.id is not None
    assert entry.entity_type == "reservation"
    assert entry.action == "create"
    assert entry.actor_id == user.id

    result = await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    log = result.scalar_one()
    assert json.loads(log.changes) == {"venue_id": 1, "start": "2026-06-01T10:00:00"}


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_service_no_changes(db_session: AsyncSession):
    from app.services.audit import audit_log

    entry = await audit_log(
        db_session,
        entity_type="venue",
        entity_id=1,
        action="archive",
        actor_id=None,
    )
    assert entry.changes is None
    assert entry.actor_id is None
