import datetime
from typing import Optional

from sqlalchemy import String, Integer, Time, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class VenueAvailability(Base):
    __tablename__ = "venue_availability"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="chk_availability_dow"),
        UniqueConstraint("venue_id", "day_of_week", "start_time", "end_time", name="uq_availability_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
