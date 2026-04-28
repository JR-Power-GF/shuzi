"""Tests for XR callback endpoint, session listing, and retry endpoint.

TDD RED phase — all tests written before implementation.

Covers:
  1. Callback receive: processed, duplicate, missing fields
  2. Signature verification: valid/invalid/disabled
  3. Feature flag: disabled → 503
  4. Session listing: admin 200, teacher 403
  5. Retry endpoint: success, disabled
"""
import hashlib
import hmac
import json

import pytest

from app.config import settings
from app.models.xr_session import XRSession
from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_booking,
    login_user,
    auth_headers,
)


async def _admin_token(client, db):
    admin = await create_test_user(db, username="xr-ep-admin", role="admin")
    venue = await create_test_venue(db, name="XR EP Venue")
    booking = await create_test_booking(db, venue_id=venue.id, booked_by=admin.id)
    token = await login_user(client, "xr-ep-admin")
    return booking, token


# ===================================================================
# POST /api/v1/xr/callbacks
# ===================================================================


class TestReceiveCallback:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_processed(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "")

        resp = await client.post("/api/v1/xr/callbacks", json={
            "event_id": "ep-001",
            "provider": "null",
            "event_type": "session.started",
            "data": {"key": "val"},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processed"
        assert body["event_id"] == "ep-001"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_duplicate_returns_already_processed(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "")

        payload = {"event_id": "ep-dup", "provider": "null", "event_type": "test"}
        r1 = await client.post("/api/v1/xr/callbacks", json=payload)
        assert r1.json()["status"] == "processed"

        r2 = await client.post("/api/v1/xr/callbacks", json=payload)
        assert r2.json()["status"] == "already_processed"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_missing_event_id_returns_400(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        resp = await client.post("/api/v1/xr/callbacks", json={
            "provider": "null", "event_type": "test",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio(loop_scope="session")
    async def test_invalid_signature_returns_401(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "my-secret")

        resp = await client.post(
            "/api/v1/xr/callbacks",
            json={"event_id": "ep-sig-bad", "provider": "null", "event_type": "test"},
            headers={"X-XR-Signature": "wrong-signature"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio(loop_scope="session")
    async def test_valid_signature_returns_200(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "my-secret")

        payload = {"event_id": "ep-sig-ok", "provider": "null", "event_type": "test"}
        body_bytes = json.dumps(payload).encode()
        sig = hmac.new(b"my-secret", body_bytes, hashlib.sha256).hexdigest()

        # Send raw bytes so the exact body matches the HMAC computation.
        # Using json= would let httpx re-serialize (compact), breaking the signature.
        resp = await client.post(
            "/api/v1/xr/callbacks",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-XR-Signature": sig,
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio(loop_scope="session")
    async def test_disabled_returns_503(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", False)
        resp = await client.post("/api/v1/xr/callbacks", json={
            "event_id": "ep-off", "provider": "null", "event_type": "test",
        })
        assert resp.status_code == 503


# ===================================================================
# GET /api/v1/xr/sessions
# ===================================================================


class TestListXRSessions:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_admin_can_list_sessions(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking, token = await _admin_token(client, db_session)

        xr = XRSession(booking_id=booking.id, provider="null", status="completed")
        db_session.add(xr)
        await db_session.flush()

        resp = await client.get("/api/v1/xr/sessions", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio(loop_scope="session")
    async def test_teacher_forbidden(self, client, db_session):
        teacher = await create_test_user(db_session, username="xr-ep-teacher", role="teacher")
        token = await login_user(client, "xr-ep-teacher")

        resp = await client.get("/api/v1/xr/sessions", headers=auth_headers(token))
        assert resp.status_code == 403


# ===================================================================
# POST /api/v1/xr/sessions/{id}/retry
# ===================================================================


class TestRetryXRSessionsEndpoint:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_retry_failed_session_200(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking, token = await _admin_token(client, db_session)

        xr = XRSession(
            booking_id=booking.id, provider="null", status="failed",
            error_message="timeout", retry_count=0,
        )
        db_session.add(xr)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/xr/sessions/{xr.id}/retry",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio(loop_scope="session")
    async def test_retry_when_disabled_returns_503(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", False)
        admin = await create_test_user(db_session, username="xr-ep-retryoff", role="admin")
        token = await login_user(client, "xr-ep-retryoff")

        resp = await client.post(
            "/api/v1/xr/sessions/999/retry", headers=auth_headers(token),
        )
        assert resp.status_code == 503
