"""XR service — background tasks, callback processing, retry, and signature verification.

Design decisions:
- Background task functions (create_xr_session_for_booking, cancel_xr_session_for_booking)
  open their own database session via async_session_maker(), because they run as
  FastAPI BackgroundTasks outside the request lifecycle.
- process_callback_event and retry_failed_session take a db session parameter from the
  caller (the endpoint), so they participate in the request transaction.
- verify_callback_signature is a pure function (HMAC-SHA256).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker as _default_session_maker, _utcnow_naive
from app.models.xr_event import XREvent
from app.models.xr_session import XRSession
from app.services.xr_provider import get_xr_provider, XRResult

logger = logging.getLogger(__name__)

# Overridable session factory for background tasks.
# In production this uses the default async_session_maker from app.database.
# In tests this can be monkeypatched to use the test session maker.
_session_factory = _default_session_maker


# ---------------------------------------------------------------------------
# Background task: create XR session for a booking
# ---------------------------------------------------------------------------


async def create_xr_session_for_booking(booking_id: int) -> None:
    """Background task: create an XR session for a booking.

    Opens its own database session because it runs outside the request lifecycle.
    For NullXRProvider the session is immediately set to 'completed'.
    If the provider errors, the session is set to 'failed'.
    Handles being called twice for the same booking_id (unique constraint) by
    checking if a session already exists.
    """
    if not settings.XR_ENABLED:
        return

    async with _session_factory() as db:
        try:
            # Check if session already exists for this booking (idempotent)
            existing = await db.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            if existing.scalar_one_or_none() is not None:
                logger.info("XR session already exists for booking %s, skipping", booking_id)
                return

            xr = XRSession(
                booking_id=booking_id,
                provider=settings.XR_PROVIDER,
                status="pending",
                request_payload=json.dumps({"booking_id": booking_id}),
            )
            db.add(xr)
            await db.flush()

            provider = get_xr_provider()
            result: XRResult = await provider.create_session(booking_id=booking_id)

            if result.success:
                xr.status = "completed"
                xr.external_session_id = result.external_session_id
                if result.raw_response:
                    xr.response_payload = json.dumps(result.raw_response)
            else:
                xr.status = "failed"
                xr.error_message = result.error or "Unknown provider error"

            await db.commit()
        except Exception:
            await db.rollback()
            raise


# ---------------------------------------------------------------------------
# Background task: cancel XR session for a booking
# ---------------------------------------------------------------------------


async def cancel_xr_session_for_booking(booking_id: int) -> None:
    """Background task: cancel an existing XR session for a booking.

    Opens its own database session. If no session exists, this is a no-op.
    """
    if not settings.XR_ENABLED:
        return

    async with _session_factory() as db:
        try:
            result = await db.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            xr = result.scalar_one_or_none()
            if xr is None:
                return

            # Call provider to cancel the external session
            if xr.external_session_id:
                provider = get_xr_provider()
                await provider.cancel_session(session_id=xr.external_session_id)

            xr.status = "cancelled"
            await db.commit()
        except Exception:
            await db.rollback()
            raise


# ---------------------------------------------------------------------------
# Callback event processing
# ---------------------------------------------------------------------------


async def process_callback_event(
    db: AsyncSession,
    *,
    event_id: str,
    provider: str,
    event_type: str,
    payload: Optional[dict | str] = None,
    idempotency_key: Optional[str] = None,
    signature_verified: bool = False,
) -> bool:
    """Process an incoming callback event.

    Takes the db session from the caller (the endpoint).
    Returns True if the event was newly created, False if it was a duplicate.
    Deduplicates by event_id and idempotency_key.
    Updates XRSession status when payload contains booking_id.
    """
    # Dedup by event_id
    existing = await db.execute(
        select(XREvent).where(XREvent.event_id == event_id)
    )
    if existing.scalar_one_or_none() is not None:
        return False

    # Dedup by idempotency_key (if provided)
    if idempotency_key:
        existing_key = await db.execute(
            select(XREvent).where(XREvent.idempotency_key == idempotency_key)
        )
        if existing_key.scalar_one_or_none() is not None:
            return False

    # Determine booking_id from payload if present
    booking_id: Optional[int] = None
    xr_session_id: Optional[int] = None
    payload_str: Optional[str] = None

    if payload is not None:
        if isinstance(payload, dict):
            payload_str = json.dumps(payload)
            booking_id = payload.get("booking_id")
        else:
            payload_str = payload

    # Look up the XR session by booking_id
    if booking_id is not None:
        session_result = await db.execute(
            select(XRSession).where(XRSession.booking_id == booking_id)
        )
        xr_session = session_result.scalar_one_or_none()
        if xr_session is not None:
            xr_session_id = xr_session.id

            # Update session status based on event type
            status_map = {
                "session.started": "active",
                "session.completed": "completed",
                "session.failed": "failed",
                "session.cancelled": "cancelled",
            }
            new_status = status_map.get(event_type)
            if new_status:
                xr_session.status = new_status
                await db.flush()

    now = _utcnow_naive()
    event = XREvent(
        event_id=event_id,
        booking_id=booking_id,
        xr_session_id=xr_session_id,
        provider=provider,
        event_type=event_type,
        payload=payload_str,
        idempotency_key=idempotency_key,
        signature_verified=signature_verified,
        processed=True,
        processed_at=now,
    )
    db.add(event)

    return True


# ---------------------------------------------------------------------------
# Retry failed session
# ---------------------------------------------------------------------------


async def retry_failed_session(db: AsyncSession, session_id: int) -> XRResult:
    """Retry a failed XR session.

    Takes the db session from the caller.
    Returns XRResult indicating success or failure.
    """
    if not settings.XR_ENABLED:
        return XRResult(success=False, error="XR is disabled")

    result = await db.execute(
        select(XRSession).where(XRSession.id == session_id)
    )
    xr = result.scalar_one_or_none()
    if xr is None:
        return XRResult(success=False, error=f"XR session {session_id} not found")

    if xr.status != "failed":
        return XRResult(success=False, error=f"XR session is not in failed state (current: {xr.status})")

    provider = get_xr_provider()
    provider_result: XRResult = await provider.create_session(booking_id=xr.booking_id)

    xr.retry_count += 1
    xr.last_retry_at = _utcnow_naive()

    if provider_result.success:
        xr.status = "completed"
        xr.error_message = None
        if provider_result.external_session_id:
            xr.external_session_id = provider_result.external_session_id
    else:
        xr.error_message = provider_result.error or "Retry failed"

    await db.flush()

    return XRResult(success=provider_result.success)


# ---------------------------------------------------------------------------
# Signature verification (pure function)
# ---------------------------------------------------------------------------


def verify_callback_signature(
    secret: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify HMAC-SHA256 callback signature.

    Returns True when secret is empty (skip verification).
    Returns True when the computed signature matches the provided one.
    Returns False otherwise.
    """
    if not secret:
        return True

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
