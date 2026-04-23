import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin1", password="admin1234", role="admin")
    token = await login_user(client, "admin1", "admin1234")

    resp = await client.post(
        "/api/users",
        json={
            "username": "new_teacher",
            "password": "teacher1234",
            "real_name": "张老师",
            "role": "teacher",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "new_teacher"
    assert data["role"] == "teacher"
    assert data["must_change_password"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user_duplicate(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_dup", password="admin1234", role="admin")
    await create_test_user(db_session, username="existing", password="pass1234")
    token = await login_user(client, "admin_dup", "admin1234")

    resp = await client.post(
        "/api/users",
        json={"username": "existing", "password": "pass1234", "real_name": "重复", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user_forbidden(client, db_session):
    from tests.helpers import create_test_user, login_user

    teacher = await create_test_user(db_session, username="teacher_noauth", password="pass1234", role="teacher")
    token = await login_user(client, "teacher_noauth", "pass1234")

    resp = await client.post(
        "/api/users",
        json={"username": "some", "password": "pass1234", "real_name": "名", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_users(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_list", password="admin1234", role="admin")
    await create_test_user(db_session, username="s1", password="pass1234", role="student", real_name="学生一")
    await create_test_user(db_session, username="s2", password="pass1234", role="student", real_name="学生二")
    token = await login_user(client, "admin_list", "admin1234")

    resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3


@pytest.mark.asyncio(loop_scope="session")
async def test_list_users_filter_role(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_filter", password="admin1234", role="admin")
    await create_test_user(db_session, username="t1", password="pass1234", role="teacher")
    await create_test_user(db_session, username="s3", password="pass1234", role="student")
    token = await login_user(client, "admin_filter", "admin1234")

    resp = await client.get(
        "/api/users?role=teacher",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(u["role"] == "teacher" for u in data["items"])


@pytest.mark.asyncio(loop_scope="session")
async def test_get_me(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="me_user", password="pass1234")
    token = await login_user(client, "me_user", "pass1234")

    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "me_user"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_me(client, db_session):
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="updateme", password="pass1234")
    token = await login_user(client, "updateme", "pass1234")

    resp = await client.put(
        "/api/users/me",
        json={"real_name": "新名字", "email": "new@test.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["real_name"] == "新名字"
    assert resp.json()["email"] == "new@test.com"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_user_admin(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_upd", password="admin1234", role="admin")
    target = await create_test_user(db_session, username="target_user", password="pass1234")
    token = await login_user(client, "admin_upd", "admin1234")

    resp = await client.put(
        f"/api/users/{target.id}",
        json={"real_name": "被改名", "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["real_name"] == "被改名"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio(loop_scope="session")
async def test_deactivate_user(client, db_session):
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_deact", password="admin1234", role="admin")
    target = await create_test_user(db_session, username="deact_target", password="pass1234")
    token = await login_user(client, "admin_deact", "admin1234")

    resp = await client.put(
        f"/api/users/{target.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Deactivated user can't login
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "deact_target", "password": "pass1234"},
    )
    assert login_resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_update_me_cannot_set_is_active(client, db_session):
    """P0 fix: students must not be able to set is_active via PUT /me."""
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="no_self_deact", password="pass1234")
    token = await login_user(client, "no_self_deact", "pass1234")

    resp = await client.put(
        "/api/users/me",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_update_me_cannot_set_primary_class_id(client, db_session):
    """P0 fix: students must not be able to set primary_class_id via PUT /me."""
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="no_class_set", password="pass1234")
    token = await login_user(client, "no_class_set", "pass1234")

    resp = await client.put(
        "/api/users/me",
        json={"primary_class_id": 999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_can_set_is_active(client, db_session):
    """Admin PUT /:id should still be able to set is_active and primary_class_id."""
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_active", password="admin1234", role="admin")
    target = await create_test_user(db_session, username="active_target", password="pass1234")
    token = await login_user(client, "admin_active", "admin1234")

    resp = await client.put(
        f"/api/users/{target.id}",
        json={"is_active": False, "primary_class_id": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
