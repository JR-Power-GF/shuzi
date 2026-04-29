"""XR callback endpoint and admin session management."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import require_role
from app.models.xr_session import XRSession
from app.schemas.xr import (
    XRSessionListResponse,
    XRSessionResponse,
    XRSessionRetryResponse,
    XRCallbackResponse,
)
from app.services.xr_service import (
    process_callback_event,
    retry_failed_session,
    verify_callback_signature,
)

router = APIRouter(prefix="/api/v1/xr", tags=["xr"])


# ---------------------------------------------------------------------------
# POST /api/v1/xr/callbacks — public (no auth)
# ---------------------------------------------------------------------------


@router.post("/callbacks", response_model=XRCallbackResponse)
async def receive_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process an XR provider callback.

    Public endpoint — no authentication required.
    Verifies HMAC-SHA256 signature when XR_CALLBACK_SECRET is configured.
    Deduplicates by event_id and idempotency_key.
    """
    if not settings.XR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="XR integration is disabled",
        )

    # Read raw body for signature verification
    body_bytes = await request.body()

    # Signature verification
    secret = settings.XR_CALLBACK_SECRET
    if secret:
        sig_header = request.headers.get("X-XR-Signature", "")
        if not verify_callback_signature(secret, body_bytes, sig_header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid signature",
            )

    # Parse JSON payload
    try:
        data = json.loads(body_bytes)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_id = data.get("event_id")
    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event_id",
        )

    provider = data.get("provider", "null")
    event_type = data.get("event_type", "unknown")
    payload_data = data.get("data") or data.get("payload")
    idempotency_key = data.get("idempotency_key")

    is_new = await process_callback_event(
        db,
        event_id=event_id,
        provider=provider,
        event_type=event_type,
        payload=payload_data,
        idempotency_key=idempotency_key,
        signature_verified=bool(secret),
    )

    if is_new:
        return XRCallbackResponse(status="processed", event_id=event_id)
    else:
        return XRCallbackResponse(status="already_processed", event_id=event_id)


# ---------------------------------------------------------------------------
# GET /api/v1/xr/sessions — admin/facility_manager only
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=XRSessionListResponse)
async def list_xr_sessions(
    status_filter: str | None = Query(None, alias="status"),
    provider: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    """List XR sessions with optional status/provider filters.

    Admin and facility_manager only.
    """
    query = select(XRSession)
    count_query = select(func.count()).select_from(XRSession)

    if status_filter:
        query = query.where(XRSession.status == status_filter)
        count_query = count_query.where(XRSession.status == status_filter)

    if provider:
        query = query.where(XRSession.provider == provider)
        count_query = count_query.where(XRSession.provider == provider)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(XRSession.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    sessions = result.scalars().all()

    return XRSessionListResponse(
        items=[XRSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/xr/sessions/{session_id}/retry — admin/facility_manager only
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/retry", response_model=XRSessionRetryResponse)
async def retry_session(
    session_id: int,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed XR session.

    Admin and facility_manager only.
    """
    if not settings.XR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="XR integration is disabled",
        )

    result = await retry_failed_session(db, session_id)

    if not result.success:
        if "not found" in (result.error or ""):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error,
            )
        if "not in failed state" in (result.error or ""):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.error,
            )
        # For other errors (e.g. provider error), still return 200 with failed status
        return XRSessionRetryResponse(
            session_id=session_id,
            status="failed",
            message=result.error or "Retry failed",
        )

    return XRSessionRetryResponse(
        session_id=session_id,
        status="completed",
        message="Retry succeeded",
    )
