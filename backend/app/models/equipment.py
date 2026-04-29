import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="chk_equipment_status"),
        Index("ix_equipment_external_id", "external_id"),
        Index("ix_equipment_serial_number", "serial_number", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    venue_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("venues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )
