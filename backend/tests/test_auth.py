import pytest
import bcrypt
from sqlalchemy import select


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success(client, db_session):
    import bcrypt
    from app.models.user import User

    pw_hash = bcrypt.hashpw(b"teacher123", bcrypt.gensalt()).decode("utf-8")
    user = User(
        username="teacher1", password_hash=pw_hash,
        real_name="王老师", role="teacher", must_change_password=True,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "teacher1", "password": "teacher123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["must_change_password"] is True
    assert data["user"]["id"] == user.id
    assert data["user"]["username"] == "teacher1"
    assert data["user"]["real_name"] == "王老师"
    assert data["user"]["role"] == "teacher"


@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_password(client, db_session):
    import bcrypt
    from app.models.user import User

    pw_hash = bcrypt.hashpw(b"teacher123", bcrypt.gensalt()).decode("utf-8")
    user = User(username="teacher1", password_hash=pw_hash, real_name="王老师", role="teacher")
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "teacher1", "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_login_nonexistent_user(client, db_session):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_login_inactive_user(client, db_session):
    import bcrypt
    from app.models.user import User

    pw_hash = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode("utf-8")
    user = User(
        username="disabled", password_hash=pw_hash,
        real_name="禁用", role="student", is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "disabled", "password": "pass123"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_login_locked_account(client, db_session):
    import datetime
    import bcrypt
    from app.models.user import User

    pw_hash = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode("utf-8")
    user = User(
        username="locked_user", password_hash=pw_hash,
        real_name="锁定", role="student",
        locked_until=datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "locked_user", "password": "pass123"},
    )
    assert resp.status_code == 403
    assert "锁定" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_account_lockout_after_threshold(test_session_maker):
    """FAIL-002 fix: failed_login_attempts must persist across requests.

    Uses a production-like get_db (commit on success, rollback on exception)
    to verify that the counter survives the request lifecycle.
    """
    from app.models.user import User
    from app.config import settings
    from httpx import AsyncClient, ASGITransport
    from app.main import app as fastapi_app
    from app.database import get_db

    # 1. Create user and commit to DB
    async with test_session_maker() as setup_session:
        pw_hash = bcrypt.hashpw(b"correct1234", bcrypt.gensalt()).decode()
        user = User(
            username="lockout_user", password_hash=pw_hash,
            real_name="锁定测试", role="student",
        )
        setup_session.add(user)
        await setup_session.commit()

    # 2. Override get_db with production-like behavior (commit on success)
    async def production_get_db():
        async with test_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = production_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 3. Send LOCKOUT_THRESHOLD wrong passwords
        for i in range(settings.LOCKOUT_THRESHOLD):
            resp = await ac.post(
                "/api/auth/login",
                json={"username": "lockout_user", "password": "wrongpass123"},
            )
            assert resp.status_code == 401

        # 4. Correct password should be locked (403)
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "lockout_user", "password": "correct1234"},
        )
        assert resp.status_code == 403
        assert "锁定" in resp.json()["detail"]

    fastapi_app.dependency_overrides.clear()

    # 5. Cleanup
    async with test_session_maker() as cleanup:
        result = await cleanup.execute(
            select(User).where(User.username == "lockout_user")
        )
        if result.scalar_one_or_none():
            await cleanup.execute(
                User.__table__.delete().where(User.username == "lockout_user")
            )
            await cleanup.commit()
