import pytest
from tests.helpers import create_test_user, create_test_class, login_user, auth_headers


@pytest.mark.asyncio(loop_scope="session")
async def test_create_class_success(client, db_session):
    admin = await create_test_user(db_session, username="admin1", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher1", role="teacher", real_name="王老师")
    token = await login_user(client, "admin1")

    resp = await client.post(
        "/api/classes",
        json={"name": "计算机网络1班", "semester": "2025-2026-2", "teacher_id": teacher.id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "计算机网络1班"
    assert data["semester"] == "2025-2026-2"
    assert data["teacher_id"] == teacher.id
    assert data["teacher_name"] == "王老师"
    assert data["student_count"] == 0
    assert "id" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_create_class_forbidden_for_teacher(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/classes",
        json={"name": "班级", "semester": "2025-2026-2"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_my_classes(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, name="计算机网络1班", teacher_id=teacher.id)
    await create_test_class(db_session, name="其他班级")

    token = await login_user(client, "teacher1")
    resp = await client.get("/api/classes/my", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "计算机网络1班"
    assert data[0]["teacher_id"] == teacher.id


@pytest.mark.asyncio(loop_scope="session")
async def test_get_class_students(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", real_name="张三", primary_class_id=cls.id)
    await create_test_user(db_session, username="stu2", role="student", real_name="李四", primary_class_id=cls.id)

    token = await login_user(client, "teacher1")
    resp = await client.get(f"/api/classes/{cls.id}/students", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {s["real_name"] for s in data}
    assert names == {"张三", "李四"}


@pytest.mark.asyncio(loop_scope="session")
async def test_get_class_students_forbidden_for_other_teacher(client, db_session):
    teacher1 = await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher1.id)

    token = await login_user(client, "teacher2")
    resp = await client.get(f"/api/classes/{cls.id}/students", headers=auth_headers(token))
    assert resp.status_code == 403
