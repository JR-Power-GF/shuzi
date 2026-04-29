"""Utility functions for booking/scheduling concurrency.

Reusable primitives that Phase 3 booking routers will call.
They do NOT depend on any booking model — they work with generic time intervals.
"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def check_time_overlap(
    db: AsyncSession,
    table,
    resource_id_column,
    resource_id: int,
    start_column,
    end_column,
    new_start: datetime,
    new_end: datetime,
    exclude_id: int | None = None,
    exclude_id_column=None,
) -> bool:
    """Check if a new time range overlaps with existing bookings for a resource.

    Returns True if there IS an overlap (i.e., the slot is taken).
    Two intervals [A_start, A_end) and [B_start, B_end) overlap iff:
        A_start < B_end AND B_start < A_end
    """
    if new_start >= new_end:
        raise ValueError("start must be before end")

    overlap_condition = and_(
        resource_id_column == resource_id,
        start_column < new_end,
        end_column > new_start,
    )

    if exclude_id is not None and exclude_id_column is not None:
        overlap_condition = and_(
            overlap_condition,
            exclude_id_column != exclude_id,
        )

    stmt = select(table).where(overlap_condition)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def acquire_row_lock(db: AsyncSession, table, row_id: int):
    """Acquire a pessimistic row lock (SELECT ... FOR UPDATE).

    Returns the locked row, or None if not found.
    """
    stmt = select(table).where(table.id == row_id).with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def handle_integrity_error(exc: Exception, detail: str = "Conflict") -> None:
    """Convert a SQLAlchemy IntegrityError to an HTTPException.

    Re-raises non-IntegrityError exceptions unchanged.
    Must be called inside an except block.
    """
    if isinstance(exc, IntegrityError):
        raise HTTPException(status_code=409, detail=detail)
    raise exc
