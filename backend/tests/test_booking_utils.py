"""Tests for booking concurrency primitives.

Uses the Class model as a stand-in for a resource with time ranges.
teacher_id = resource_id, created_at = start_time, updated_at = end_time.
"""
import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.services.booking_utils import (
    check_time_overlap,
    acquire_row_lock,
    handle_integrity_error,
)
from tests.helpers import create_test_user, create_test_class


@pytest.fixture
def t():
    """Shortcuts for datetime offsets from a base time."""
    base = datetime.datetime(2026, 6, 1, 10, 0, 0)
    return {
        "s1": base,
        "e1": base + datetime.timedelta(hours=2),
        "s2": base + datetime.timedelta(hours=3),
        "e2": base + datetime.timedelta(hours=5),
    }


async def _add_class_with_times(db: AsyncSession, teacher_id: int, name: str, created_at, updated_at):
    cls = Class(
        name=name,
        semester="2025-2026-1",
        teacher_id=teacher_id,
    )
    db.add(cls)
    await db.flush()
    cls.created_at = created_at
    cls.updated_at = updated_at
    await db.flush()
    return cls


@pytest.mark.asyncio(loop_scope="session")
async def test_no_overlap_returns_false(db_session: AsyncSession, t):
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, 1,
        Class.created_at, Class.updated_at,
        t["s2"], t["e2"],
    )
    assert result is False


@pytest.mark.asyncio(loop_scope="session")
async def test_exact_overlap_returns_true(db_session: AsyncSession, t):
    teacher = await create_test_user(db_session, username="book_teacher_1", role="teacher")
    await _add_class_with_times(db_session, teacher.id, "overlap-test-1", t["s1"], t["e1"])
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, teacher.id,
        Class.created_at, Class.updated_at,
        t["s1"], t["e1"],
    )
    assert result is True


@pytest.mark.asyncio(loop_scope="session")
async def test_partial_overlap_returns_true(db_session: AsyncSession, t):
    teacher = await create_test_user(db_session, username="book_teacher_2", role="teacher")
    await _add_class_with_times(db_session, teacher.id, "overlap-test-2", t["s1"], t["e1"])
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, teacher.id,
        Class.created_at, Class.updated_at,
        t["s1"] + datetime.timedelta(hours=1), t["e2"],
    )
    assert result is True


@pytest.mark.asyncio(loop_scope="session")
async def test_non_overlapping_returns_false(db_session: AsyncSession, t):
    teacher = await create_test_user(db_session, username="book_teacher_3", role="teacher")
    await _add_class_with_times(db_session, teacher.id, "overlap-test-3", t["s1"], t["e1"])
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, teacher.id,
        Class.created_at, Class.updated_at,
        t["s2"], t["e2"],
    )
    assert result is False


@pytest.mark.asyncio(loop_scope="session")
async def test_adjacent_no_overlap(db_session: AsyncSession, t):
    teacher = await create_test_user(db_session, username="book_teacher_4", role="teacher")
    await _add_class_with_times(db_session, teacher.id, "overlap-test-4", t["s1"], t["e1"])
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, teacher.id,
        Class.created_at, Class.updated_at,
        t["e1"], t["e2"],
    )
    assert result is False


@pytest.mark.asyncio(loop_scope="session")
async def test_exclude_id_works(db_session: AsyncSession, t):
    teacher = await create_test_user(db_session, username="book_teacher_5", role="teacher")
    cls = await _add_class_with_times(db_session, teacher.id, "overlap-test-5", t["s1"], t["e1"])
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, teacher.id,
        Class.created_at, Class.updated_at,
        t["s1"], t["e1"],
        exclude_id=cls.id, exclude_id_column=Class.id,
    )
    assert result is False


@pytest.mark.asyncio(loop_scope="session")
async def test_start_after_end_raises(db_session: AsyncSession, t):
    with pytest.raises(ValueError, match="start must be before end"):
        await check_time_overlap(
            db_session, Class, Class.teacher_id, 1,
            Class.created_at, Class.updated_at,
            t["e1"], t["s1"],
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_acquire_row_lock(db_session: AsyncSession):
    cls = await create_test_class(db_session, name="lock-test-class")
    locked = await acquire_row_lock(db_session, Class, cls.id)
    assert locked is not None
    assert locked.id == cls.id


@pytest.mark.asyncio(loop_scope="session")
async def test_acquire_row_lock_not_found(db_session: AsyncSession):
    locked = await acquire_row_lock(db_session, Class, 999999)
    assert locked is None


def test_handle_integrity_error():
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        try:
            raise IntegrityError("", "", Exception())
        except Exception as e:
            handle_integrity_error(e, "Duplicate booking")
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Duplicate booking"


def test_handle_integrity_error_reraises_non_integrity():
    with pytest.raises(RuntimeError):
        try:
            raise RuntimeError("something else")
        except Exception as e:
            handle_integrity_error(e)


@pytest.mark.asyncio(loop_scope="session")
async def test_different_resource_no_overlap(db_session: AsyncSession, t):
    """Overlap check for resource_id=2 should not find bookings for resource_id=1."""
    teacher = await create_test_user(db_session, username="book_teacher_6", role="teacher")
    await _add_class_with_times(db_session, teacher.id, "resource-1", t["s1"], t["e1"])
    result = await check_time_overlap(
        db_session, Class, Class.teacher_id, teacher.id + 999,
        Class.created_at, Class.updated_at,
        t["s1"], t["e1"],
    )
    assert result is False
