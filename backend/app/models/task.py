import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    deadline: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    allowed_file_types: Mapped[str] = mapped_column(Text, nullable=False)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    allow_late_submission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_penalty_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    grades_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grades_published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    grades_published_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="chk_task_status"),
    )
