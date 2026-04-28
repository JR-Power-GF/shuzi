"""Integration tests: booking lifecycle ↔ XR session lifecycle.

TDD RED phase — all tests written before implementation.

Core guarantee tested: local booking NEVER depends on XR success.

Covers:
  1. Booking creation triggers XR session
  2. Booking succeeds when XR is disabled (no session)
  3. Booking cancellation triggers XR cancel
  4. Booking succeeds even when XR provider fails (isolation)
  5. Duplicate background-task call does not create duplicate XR session
"""
import pytest
from sqlalchemy import select

from app.config import settings
from app.models.booking import Booking
from app.models.xr_session import XRSession
from app.services.xr_provider import XRResult
from app.database import async_session_maker
from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_booking,
)


async def _committed_booking(test_session_maker, *, username, venue_name):
    async with test_session_maker() as s:
        user = await create_test_user(s, username=username, role="admin")
        venue = await create_test_venue(s, name=venue_name)
        booking = await create_test_booking(s, venue_id=venue.id, booked_by=user.id)
        await s.commit()
        return booking.id


def _patch_session_factory(monkeypatch, test_session_maker):
    import app.services.xr_service as _mod
    monkeypatch.setattr(_mod, "_session_factory", test_session_maker)


class TestBookingTriggersXR:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_booking_creates_xr_session(self, test_session_maker, monkeypatch):
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-int-ok", venue_name="XR Int OK",
        )

        await create_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            xr = (await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )).scalar_one()
            assert xr.status == "completed"
            assert xr.provider == "null"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_no_xr_session_when_disabled(self, test_session_maker, monkeypatch):
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", False)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-int-off", venue_name="XR Int Off",
        )

        await create_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            result = await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_cancel_booking_cancels_xr_session(self, test_session_maker, monkeypatch):
        from app.services.xr_service import (
            create_xr_session_for_booking,
            cancel_xr_session_for_booking,
        )

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-int-cancel", venue_name="XR Int Cancel",
        )

        await create_xr_session_for_booking(booking_id)
        await cancel_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            xr = (await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )).scalar_one()
            assert xr.status == "cancelled"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_booking_succeeds_when_xr_provider_fails(self, test_session_maker, monkeypatch):
        """Core isolation guarantee: booking is committed before XR runs.

        Even if the XR provider fails, the booking must persist.
        """
        from app.services import xr_provider as xp
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        original = xp._PROVIDER_REGISTRY.copy()

        class FailProvider(xp.NullXRProvider):
            @property
            def name(self):
                return "null"

            async def create_session(self, *, booking_id):
                return XRResult(success=False, error="simulated failure")

        xp._PROVIDER_REGISTRY["null"] = FailProvider
        try:
            booking_id = await _committed_booking(
                test_session_maker, username="xr-int-fail", venue_name="XR Int Fail",
            )

            # Booking was committed before XR
            async with test_session_maker() as s:
                found = (await s.execute(
                    select(Booking).where(Booking.id == booking_id)
                )).scalar_one()
                assert found.status == "approved"

            # XR session records failure
            await create_xr_session_for_booking(booking_id)

            async with test_session_maker() as s:
                xr = (await s.execute(
                    select(XRSession).where(XRSession.booking_id == booking_id)
                )).scalar_one()
                assert xr.status == "failed"
                assert xr.error_message is not None
        finally:
            xp._PROVIDER_REGISTRY = original

    @pytest.mark.asyncio(loop_scope="session")
    async def test_duplicate_background_call_no_extra_xr_session(self, test_session_maker, monkeypatch):
        """Calling background task twice for same booking must not duplicate XR session."""
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-int-idem", venue_name="XR Int Idem",
        )

        await create_xr_session_for_booking(booking_id)
        # Second call should handle unique constraint gracefully
        await create_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            sessions = (await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )).scalars().all()
            assert len(sessions) == 1
