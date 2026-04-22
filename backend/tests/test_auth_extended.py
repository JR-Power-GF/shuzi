import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_success(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="refresh_user", password="pass1234")
    # Login to get both tokens
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "refresh_user", "password": "pass1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_revoked_token(client, db_session):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="revoke_user", password="pass1234")
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "revoke_user", "password": "pass1234"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout first
    token = login_resp.json()["access_token"]
    await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_success(client, db_session):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="logout_user", password="pass1234")
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "logout_user", "password": "pass1234"},
    )
    token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "成功" in resp.json()["message"]
