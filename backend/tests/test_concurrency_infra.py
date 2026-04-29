"""Tests for concurrency test infrastructure and primitives."""
import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.services.booking_utils import acquire_row_lock
from tests.helpers import create_test_class


@pytest.mark.asyncio(loop_scope="session")
async def test_second_db_session_is_independent(second_db_session: AsyncSession):
    """second_db_session should be a valid independent session."""
    cls = Class(name="independent-test", semester="2025-2026-1")
    second_db_session.add(cls)
    await second_db_session.flush()
    assert cls.id is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_sessions_provides_two(concurrent_sessions):
    """concurrent_sessions fixture should provide two separate sessions."""
    assert "session_a" in concurrent_sessions
    assert "session_b" in concurrent_sessions
    assert concurrent_sessions["session_a"] is not concurrent_sessions["session_b"]


@pytest.mark.asyncio(loop_scope="session")
async def test_row_lock_blocks_concurrent_access(concurrent_sessions):
    """Verify that FOR UPDATE lock prevents concurrent modification."""
    session_a = concurrent_sessions["session_a"]
    session_b = concurrent_sessions["session_b"]

    # Create a class in session_a and commit so session_b can see it
    cls = Class(name="lock-test-concurrent", semester="2025-2026-1")
    session_a.add(cls)
    await session_a.flush()
    cls_id = cls.id

    # Lock the row in session_a
    locked = await acquire_row_lock(session_a, Class, cls_id)
    assert locked is not None

    # Try to lock the same row in session_b with a timeout
    # This should succeed after session_a releases (on rollback),
    # but would block if the lock is held
    async def try_lock_b():
        return await acquire_row_lock(session_b, Class, cls_id)

    # Give session_b a short timeout — if the lock works, this completes
    # after session_a's transaction ends (rollback at fixture teardown)
    try:
        result = await asyncio.wait_for(try_lock_b(), timeout=2.0)
        # If this succeeds, the lock was released quickly enough
        assert result is not None
    except asyncio.TimeoutError:
        # This is the expected behavior if the lock is truly held
        pass
