import pytest


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
    assert resp.status_code == 401


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
