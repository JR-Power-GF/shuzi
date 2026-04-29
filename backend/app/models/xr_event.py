"""XR event log — records incoming callbacks and external events."""
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class XREvent(Base):
    __tablename__ = "xr_events"
    __table_args__ = (
        Index("ix_xr_events_event_id", "event_id", unique=True),
        Index("ix_xr_events_idempotency_key", "idempotency_key", unique=True),
        Index("ix_xr_events_booking_id", "booking_id"),
        Index("ix_xr_events_provider_type", "provider", "event_type"),
        Index("ix_xr_events_processed", "processed"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    booking_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True
    )
    xr_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("xr_sessions.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
