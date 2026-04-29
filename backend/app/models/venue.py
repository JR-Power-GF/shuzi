import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="chk_venue_status"),
        Index("ix_venues_external_id", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )
