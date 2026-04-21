import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_database_engine_created():
    from app.database import engine

    assert engine is not None
    assert "aiomysql" in str(engine.url)


@pytest.mark.asyncio
async def test_database_session_can_connect():
    from app.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1


def test_base_is_declarative():
    from app.database import Base

    assert Base is not None
    assert hasattr(Base, "metadata")
