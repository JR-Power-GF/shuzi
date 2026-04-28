import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app as fastapi_app
import app.models  # noqa: F401 — ensure all models are registered with Base

# ---------------------------------------------------------------------------
# Test database (same MySQL server, separate database)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "/training_platform", "/training_platform_test"
)


# ---------------------------------------------------------------------------
# Session-scoped engine fixture: created inside the event loop
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Create the async engine once per test session, inside the event loop."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_session_maker(test_engine):
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


# ---------------------------------------------------------------------------
# Session-scoped fixtures: create / drop tables once per test session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def setup_test_db(test_engine):
    """Create all tables once per test session; drop them on session exit."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop all tables, handling circular foreign-key dependencies (users <-> classes)
    # by disabling FK checks and dropping each table individually.
    async with test_engine.begin() as conn:
        table_names = list(Base.metadata.tables.keys())
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tbl in table_names:
            await conn.execute(text(f"DROP TABLE IF EXISTS `{tbl}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_session_maker):
    """Provide a clean database session for each test.

    The session is rolled back after the test so subsequent tests start
    with a clean slate.
    """
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session: AsyncSession):
    """Provide an async HTTP test client with the DB session overridden."""

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def second_db_session(test_session_maker):
    """Provide a SECOND independent session for concurrency tests."""
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def concurrent_sessions(test_session_maker):
    """Provide TWO independent sessions for concurrent access testing."""
    async with test_session_maker() as session_a:
        async with test_session_maker() as session_b:
            yield {"session_a": session_a, "session_b": session_b}
            await session_b.rollback()
        await session_a.rollback()


@pytest.fixture
def upload_dir(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "tmp").mkdir()

    original_upload_dir = settings.UPLOAD_DIR
    original_tmp_dir = settings.UPLOAD_TMP_DIR

    settings.UPLOAD_DIR = str(uploads)
    settings.UPLOAD_TMP_DIR = str(uploads / "tmp")

    yield str(uploads)

    settings.UPLOAD_DIR = original_upload_dir
    settings.UPLOAD_TMP_DIR = original_tmp_dir
