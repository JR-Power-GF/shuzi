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
