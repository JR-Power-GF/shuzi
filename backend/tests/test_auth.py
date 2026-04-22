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
