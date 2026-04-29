"""Tests for XRSession and XREvent models.

Covers:
  1. XRSession basic CRUD and defaults
  2. XRSession unique booking_id constraint
  3. XREvent basic creation and defaults
  4. XREvent event_id dedup
  5. XREvent idempotency_key dedup
  6. XREvent nullable booking_id
"""
import pytest
from sqlalchemy import select

from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_booking,
)


async def _make_booking(db, *, username, venue_name):
    """Helper to create a committed booking for FK references."""
    user = await create_test_user(db, username=username, role="admin")
    venue = await create_test_venue(db, name=venue_name)
    booking = await create_test_booking(db, venue_id=venue.id, booked_by=user.id)
    await db.flush()
    return booking


class TestXRSessionModel:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_basic(self, db_session):
        from app.models.xr_session import XRSession

        booking = await _make_booking(db_session, username="xr-mod-1", venue_name="XR Mod 1")
        xr = XRSession(booking_id=booking.id, provider="null", status="pending")
        db_session.add(xr)
        await db_session.flush()

        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking.id)
        )
        found = result.scalar_one()
        assert found.provider == "null"
        assert found.status == "pending"
        assert found.retry_count == 0
        assert found.external_session_id is None
        assert found.error_message is None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_unique_booking_id_constraint(self, db_session):
        from app.models.xr_session import XRSession

        booking = await _make_booking(db_session, username="xr-mod-2", venue_name="XR Mod 2")
        xr1 = XRSession(booking_id=booking.id, provider="null", status="pending")
        db_session.add(xr1)
        await db_session.flush()

        xr2 = XRSession(booking_id=booking.id, provider="null", status="pending")
        db_session.add(xr2)
        with pytest.raises(Exception):  # IntegrityError on unique booking_id
            await db_session.flush()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_default_provider_is_null(self, db_session):
        from app.models.xr_session import XRSession

        booking = await _make_booking(db_session, username="xr-mod-3", venue_name="XR Mod 3")
        xr = XRSession(booking_id=booking.id, status="pending")
        db_session.add(xr)
        await db_session.flush()

        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking.id)
        )
        found = result.scalar_one()
        assert found.provider == "null"
        assert found.retry_count == 0


class TestXREventModel:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_basic(self, db_session):
        from app.models.xr_event import XREvent

        event = XREvent(
            event_id="evt-model-001",
            provider="null",
            event_type="session.started",
            signature_verified=True,
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(XREvent).where(XREvent.event_id == "evt-model-001")
        )
        found = result.scalar_one()
        assert found.provider == "null"
        assert found.event_type == "session.started"
        assert found.processed is False
        assert found.signature_verified is True
        assert found.processing_error is None
        assert found.processed_at is None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_unique_event_id_dedup(self, db_session):
        from app.models.xr_event import XREvent

        e1 = XREvent(event_id="evt-dup-model", provider="null", event_type="session.started")
        db_session.add(e1)
        await db_session.flush()

        e2 = XREvent(event_id="evt-dup-model", provider="null", event_type="session.completed")
        db_session.add(e2)
        with pytest.raises(Exception):  # IntegrityError on unique event_id
            await db_session.flush()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_unique_idempotency_key_dedup(self, db_session):
        from app.models.xr_event import XREvent

        e1 = XREvent(
            event_id="evt-ia", provider="null", event_type="session.started",
            idempotency_key="idem-key-001",
        )
        db_session.add(e1)
        await db_session.flush()

        e2 = XREvent(
            event_id="evt-ib", provider="null", event_type="session.completed",
            idempotency_key="idem-key-001",
        )
        db_session.add(e2)
        with pytest.raises(Exception):  # IntegrityError on unique idempotency_key
            await db_session.flush()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_nullable_booking_id_for_orphan_events(self, db_session):
        from app.models.xr_event import XREvent

        event = XREvent(
            event_id="evt-orphan-model",
            provider="null",
            event_type="system.heartbeat",
            booking_id=None,
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(XREvent).where(XREvent.event_id == "evt-orphan-model")
        )
        found = result.scalar_one()
        assert found.booking_id is None
