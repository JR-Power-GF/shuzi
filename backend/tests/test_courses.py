import pytest
from tests.helpers import create_test_user, login_user, auth_headers


@pytest.mark.asyncio(loop_scope="session")
async def test_create_course_success(client, db_session):
    teacher = await create_test_user(
        db_session, username="teacher1", role="teacher", real_name="张老师"
    )
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/courses",
        json={
            "name": "计算机网络",
            "description": "计算机网络基础课程",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "计算机网络"
    assert data["description"] == "计算机网络基础课程"
    assert data["semester"] == "2025-2026-2"
    assert data["teacher_id"] == teacher.id
    assert data["teacher_name"] == "张老师"
    assert data["status"] == "active"
    assert data["task_count"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_create_course_student_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.post(
        "/api/courses",
        json={
            "name": "计算机网络",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_create_course_duplicate_name(client, db_session):
    await create_test_user(
        db_session, username="teacher1", role="teacher"
    )
    token = await login_user(client, "teacher1")

    course_data = {
        "name": "数据结构",
        "semester": "2025-2026-2",
    }

    # First creation succeeds
    resp1 = await client.post(
        "/api/courses", json=course_data, headers=auth_headers(token)
    )
    assert resp1.status_code == 201

    # Second creation with same name+semester fails
    resp2 = await client.post(
        "/api/courses", json=course_data, headers=auth_headers(token)
    )
    assert resp2.status_code == 409
    assert "同一学期已存在同名课程" in resp2.json()["detail"]
