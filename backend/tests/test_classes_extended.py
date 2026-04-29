import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_update_class(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_cls", password="admin1234", role="admin")
    teacher = await create_test_user(db_session, username="cls_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, name="旧名称", teacher_id=teacher.id)
    token = await login_user(client, "admin_cls", "admin1234")

    resp = await client.put(
        f"/api/classes/{cls.id}",
        json={"name": "新名称"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "新名称"


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_class(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_del", password="admin1234", role="admin")
    cls = await create_test_class(db_session, name="待删除班级")
    token = await login_user(client, "admin_del", "admin1234")

    resp = await client.delete(
        f"/api/classes/{cls.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_class_with_students(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_delstu", password="admin1234", role="admin")
    cls = await create_test_class(db_session, name="有学生班级")
    student = await create_test_user(db_session, username="cls_stu", password="pass1234", primary_class_id=cls.id)
    token = await login_user(client, "admin_delstu", "admin1234")

    resp = await client.delete(
        f"/api/classes/{cls.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "学生" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_list_classes_admin(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_listcls", password="admin1234", role="admin")
    await create_test_class(db_session, name="班级A", semester="2025-2026-1")
    await create_test_class(db_session, name="班级B", semester="2025-2026-2")
    token = await login_user(client, "admin_listcls", "admin1234")

    resp = await client.get("/api/classes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_list_classes_semester_filter(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_semf", password="admin1234", role="admin")
    await create_test_class(db_session, name="过去班级", semester="2024-2025-1")
    await create_test_class(db_session, name="当前班级", semester="2025-2026-2")
    token = await login_user(client, "admin_semf", "admin1234")

    resp = await client.get(
        "/api/classes?semester=2025-2026-2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["semester"] == "2025-2026-2" for c in data["items"])


@pytest.mark.asyncio(loop_scope="session")
async def test_enroll_students(client, db_session):
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(db_session, username="admin_enroll", password="admin1234", role="admin")
    cls = await create_test_class(db_session, name="注册班级")
    s1 = await create_test_user(db_session, username="enroll_s1", password="pass1234")
    s2 = await create_test_user(db_session, username="enroll_s2", password="pass1234")
    token = await login_user(client, "admin_enroll", "admin1234")

    resp = await client.post(
        f"/api/classes/{cls.id}/students",
        json={"student_ids": [s1.id, s2.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["enrolled_count"] == 2
