"""Tests for XRService — background tasks, callback processing, retry, signature.

Covers:
  1. Background task: create XR session (enabled/disabled/failure)
  2. Background task: cancel XR session
  3. Callback processing: create event, dedup, session status update
  4. Retry: failed session retry, non-failed rejection
  5. Signature verification: HMAC valid/invalid/empty-secret
"""
import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.xr_event import XREvent
from app.models.xr_session import XRSession
from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_booking,
)


# ---------------------------------------------------------------------------
# Helper: create a committed booking that background-task sessions can see
# ---------------------------------------------------------------------------
async def _committed_booking(test_session_maker, *, username, venue_name, **kwargs):
    async with test_session_maker() as s:
        user = await create_test_user(s, username=username, role="admin")
        venue = await create_test_venue(s, name=venue_name)
        booking = await create_test_booking(
            s, venue_id=venue.id, booked_by=user.id, **kwargs
        )
        await s.commit()
        return booking.id


# Helper: patch the session factory so background tasks use the test DB
def _patch_session_factory(monkeypatch, test_session_maker):
    import app.services.xr_service as _mod
    monkeypatch.setattr(_mod, "_session_factory", test_session_maker)


# ===================================================================
# Background task: create_xr_session_for_booking
# ===================================================================


class TestCreateXRSessionBackground:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_creates_completed_session_when_enabled(self, test_session_maker, monkeypatch):
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-svc-ok", venue_name="XR SVC OK",
        )

        await create_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            result = await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            xr = result.scalar_one()
            assert xr.status == "completed"
            assert xr.provider == "null"
            assert xr.external_session_id is None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_skips_when_disabled(self, test_session_maker, monkeypatch):
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", False)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-svc-off", venue_name="XR SVC Off",
        )

        await create_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            result = await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_records_failure_when_provider_errors(self, test_session_maker, monkeypatch):
        from app.services import xr_provider as xp
        from app.services.xr_provider import XRResult
        from app.services.xr_service import create_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        original = xp._PROVIDER_REGISTRY.copy()

        class FailProvider(xp.NullXRProvider):
            @property
            def name(self):
                return "null"

            async def create_session(self, *, booking_id):
                return XRResult(success=False, error="connection refused")

        xp._PROVIDER_REGISTRY["null"] = FailProvider
        try:
            booking_id = await _committed_booking(
                test_session_maker, username="xr-svc-fail", venue_name="XR SVC Fail",
            )

            await create_xr_session_for_booking(booking_id)

            async with test_session_maker() as s:
                result = await s.execute(
                    select(XRSession).where(XRSession.booking_id == booking_id)
                )
                xr = result.scalar_one()
                assert xr.status == "failed"
                assert "connection refused" in xr.error_message
        finally:
            xp._PROVIDER_REGISTRY = original


# ===================================================================
# Background task: cancel_xr_session_for_booking
# ===================================================================


class TestCancelXRSessionBackground:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_sets_status_cancelled(self, test_session_maker, monkeypatch):
        from app.services.xr_service import (
            create_xr_session_for_booking,
            cancel_xr_session_for_booking,
        )

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-svc-cancel", venue_name="XR SVC Cancel",
        )

        await create_xr_session_for_booking(booking_id)
        await cancel_xr_session_for_booking(booking_id)

        async with test_session_maker() as s:
            result = await s.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            xr = result.scalar_one()
            assert xr.status == "cancelled"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_noop_when_no_session_exists(self, test_session_maker, monkeypatch):
        from app.services.xr_service import cancel_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-svc-nosess", venue_name="XR SVC NoSess",
        )

        # No XR session created — should not raise
        await cancel_xr_session_for_booking(booking_id)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_skips_when_disabled(self, test_session_maker, monkeypatch):
        from app.services.xr_service import cancel_xr_session_for_booking

        monkeypatch.setattr(settings, "XR_ENABLED", False)
        _patch_session_factory(monkeypatch, test_session_maker)
        booking_id = await _committed_booking(
            test_session_maker, username="xr-svc-coff", venue_name="XR SVC COff",
        )

        # Should not raise — just silently skip
        await cancel_xr_session_for_booking(booking_id)


# ===================================================================
# Callback processing: process_callback_event
# ===================================================================


class TestProcessCallbackEvent:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_creates_event_and_returns_true(self, db_session):
        from app.services.xr_service import process_callback_event

        result = await process_callback_event(
            db_session,
            event_id="evt-proc-001",
            provider="null",
            event_type="session.started",
            payload={"data": "test"},
            signature_verified=True,
        )
        assert result is True

        ev = await db_session.execute(
            select(XREvent).where(XREvent.event_id == "evt-proc-001")
        )
        event = ev.scalar_one()
        assert event.provider == "null"
        assert event.event_type == "session.started"
        assert event.signature_verified is True

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dedup_event_id_returns_false(self, db_session):
        from app.services.xr_service import process_callback_event

        await process_callback_event(
            db_session, event_id="evt-dedup", provider="null",
            event_type="session.started",
        )
        result = await process_callback_event(
            db_session, event_id="evt-dedup", provider="null",
            event_type="session.completed",
        )
        assert result is False

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dedup_idempotency_key_returns_false(self, db_session):
        from app.services.xr_service import process_callback_event

        await process_callback_event(
            db_session, event_id="evt-k1", provider="null",
            event_type="session.started", idempotency_key="key-dedup",
        )
        result = await process_callback_event(
            db_session, event_id="evt-k2", provider="null",
            event_type="session.completed", idempotency_key="key-dedup",
        )
        assert result is False

    @pytest.mark.asyncio(loop_scope="session")
    async def test_updates_xr_session_status_on_matching_booking(self, db_session, monkeypatch):
        from app.services.xr_service import process_callback_event

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        user = await create_test_user(db_session, username="xr-cb-upd", role="admin")
        venue = await create_test_venue(db_session, name="XR CB Upd")
        booking = await create_test_booking(db_session, venue_id=venue.id, booked_by=user.id)

        xr = XRSession(booking_id=booking.id, provider="null", status="pending")
        db_session.add(xr)
        await db_session.flush()

        await process_callback_event(
            db_session,
            event_id="evt-upd-001",
            provider="null",
            event_type="session.started",
            payload={"booking_id": booking.id},
        )

        await db_session.refresh(xr)
        assert xr.status == "active"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_marks_processed_with_timestamp(self, db_session):
        from app.services.xr_service import process_callback_event

        await process_callback_event(
            db_session, event_id="evt-ts-001", provider="null",
            event_type="session.started",
        )

        ev = await db_session.execute(
            select(XREvent).where(XREvent.event_id == "evt-ts-001")
        )
        event = ev.scalar_one()
        assert event.processed is True
        assert event.processed_at is not None


# ===================================================================
# Retry: retry_failed_session
# ===================================================================


class TestRetryFailedSession:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_succeeds_and_increments_retry_count(self, db_session, monkeypatch):
        from app.services.xr_service import retry_failed_session

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        user = await create_test_user(db_session, username="xr-retry-ok", role="admin")
        venue = await create_test_venue(db_session, name="XR Retry OK")
        booking = await create_test_booking(db_session, venue_id=venue.id, booked_by=user.id)

        xr = XRSession(
            booking_id=booking.id, provider="null", status="failed",
            error_message="timeout", retry_count=1,
        )
        db_session.add(xr)
        await db_session.flush()
        xr_id = xr.id

        result = await retry_failed_session(db_session, xr_id)
        assert result.success is True

        await db_session.refresh(xr)
        assert xr.retry_count == 2
        assert xr.status == "completed"
        assert xr.last_retry_at is not None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_rejects_non_failed_session(self, db_session, monkeypatch):
        from app.services.xr_service import retry_failed_session

        monkeypatch.setattr(settings, "XR_ENABLED", True)
        user = await create_test_user(db_session, username="xr-retry-comp", role="admin")
        venue = await create_test_venue(db_session, name="XR Retry Comp")
        booking = await create_test_booking(db_session, venue_id=venue.id, booked_by=user.id)

        xr = XRSession(booking_id=booking.id, provider="null", status="completed")
        db_session.add(xr)
        await db_session.flush()

        result = await retry_failed_session(db_session, xr.id)
        assert result.success is False
        assert "not in failed state" in (result.error or "")

    @pytest.mark.asyncio(loop_scope="session")
    async def test_returns_error_when_disabled(self, db_session, monkeypatch):
        from app.services.xr_service import retry_failed_session

        monkeypatch.setattr(settings, "XR_ENABLED", False)
        result = await retry_failed_session(db_session, 999)
        assert result.success is False
        assert "disabled" in (result.error or "").lower()


# ===================================================================
# Signature verification: verify_callback_signature
# ===================================================================


class TestVerifyCallbackSignature:
    def test_valid_hmac_passes(self):
        from app.services.xr_service import verify_callback_signature

        secret = "test-secret"
        body = b'{"event_id": "test"}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_callback_signature(secret, body, sig) is True

    def test_invalid_hmac_fails(self):
        from app.services.xr_service import verify_callback_signature

        assert verify_callback_signature("secret", b"body", "wrong-signature") is False

    def test_empty_secret_skips_verification(self):
        from app.services.xr_service import verify_callback_signature

        # When no secret is configured, verification is skipped (returns True)
        assert verify_callback_signature("", b"body", "") is True
