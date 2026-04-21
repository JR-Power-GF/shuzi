import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


def _make_engine():
    """Create a fresh async engine for each test to avoid event-loop reuse issues."""
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


@pytest.mark.asyncio
async def test_all_tables_created():
    engine = _make_engine()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SHOW TABLES"))
            table_names = {row[0] for row in result}

        expected = {"users", "classes", "tasks", "submissions", "submission_files", "grades", "refresh_tokens"}
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_users_table_has_correct_columns():
    engine = _make_engine()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("DESCRIBE users"))
            col_names = {row[0] for row in result}

        required = {"id", "username", "password_hash", "real_name", "role", "is_active",
                    "locked_until", "failed_login_attempts", "must_change_password",
                    "primary_class_id", "email", "phone", "created_at", "updated_at"}
        assert required.issubset(col_names), f"Missing: {required - col_names}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_submissions_unique_constraint_exists():
    engine = _make_engine()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SHOW CREATE TABLE submissions"))
            create_stmt = result.fetchone()[1]

        assert "uq_submission_task_student" in create_stmt or "UNIQUE" in create_stmt
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_grades_submission_id_unique():
    engine = _make_engine()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SHOW CREATE TABLE grades"))
            create_stmt = result.fetchone()[1]

        assert "UNIQUE" in create_stmt and "submission_id" in create_stmt
    finally:
        await engine.dispose()
