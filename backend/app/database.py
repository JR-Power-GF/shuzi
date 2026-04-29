import datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------------------------
# Patch pymysql error mapping so MySQL CHECK-constraint violations (errno 3819)
# are raised as IntegrityError rather than OperationalError.  This aligns
# with the semantic intent and matches the behaviour of other dialects.
# ---------------------------------------------------------------------------
import pymysql.err

pymysql.err.error_map[3819] = pymysql.err.IntegrityError


def _utcnow_naive() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_with_savepoint():
    """Session variant for multi-step transactions (e.g. lock + check + insert).

    Use Depends(get_db_with_savepoint) in Phase 3 booking routes where
    pessimistic locking or savepoints are needed.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
