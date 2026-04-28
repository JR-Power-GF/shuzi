import datetime
from typing import Optional

from sqlalchemy import String, Integer, SmallInteger, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (
        UniqueConstraint("ai_usage_log_id", "user_id", name="uq_feedback_log_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ai_usage_log_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_usage_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
