import datetime
from typing import Optional

from sqlalchemy import String, Integer, Date, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VenueBlackout(Base):
    __tablename__ = "venue_blackout"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="chk_blackout_date_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
