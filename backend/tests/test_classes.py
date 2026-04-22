import pytest
from tests.helpers import create_test_user, login_user, auth_headers


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
