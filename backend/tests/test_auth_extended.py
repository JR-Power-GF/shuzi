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
async def test_refresh_old_token_rejected_after_rotation(client, db_session):
    """FAIL-001 fix: old refresh token must be rejected after rotation.

    Even when both tokens are created in the same second (deterministic JWT),
    the old token must be rejected on reuse.
    """
    from tests.helpers import create_test_user

    await create_test_user(db_session, username="rotation_user", password="pass1234")
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "rotation_user", "password": "pass1234"},
    )
    old_refresh = login_resp.json()["refresh_token"]

    # Use the refresh token once — should succeed and rotate
    resp1 = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert resp1.status_code == 200
    new_refresh = resp1.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Reuse the OLD refresh token — must be rejected (401)
    resp2 = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert resp2.status_code == 401

    # New refresh token should still work
    resp3 = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert resp3.status_code == 200


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


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_success(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="changepw_user", password="oldpass123")
    token = await login_user(client, "changepw_user", "oldpass123")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Login with new password
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "changepw_user", "password": "newpass456"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_wrong_current(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="wrongpw_user", password="pass1234")
    token = await login_user(client, "wrongpw_user", "pass1234")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_too_short(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="shortpw_user", password="pass1234")
    token = await login_user(client, "shortpw_user", "pass1234")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "pass1234", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_reset_password_admin(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="reset_admin", password="admin1234", role="admin")
    student = await create_test_user(db_session, username="reset_student", password="oldpass123")

    admin_token = await login_user(client, "reset_admin", "admin1234")

    resp = await client.post(
        f"/api/auth/reset-password/{student.id}",
        json={"new_password": "resetpass1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Student can login with new password
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "reset_student", "password": "resetpass1"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["must_change_password"] is True
