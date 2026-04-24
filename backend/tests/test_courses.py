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


@pytest.mark.asyncio(loop_scope="session")
async def test_update_course_own(client, db_session):
    teacher = await create_test_user(
        db_session, username="teacher_upd1", role="teacher", real_name="李老师"
    )
    token = await login_user(client, "teacher_upd1")

    # Create a course first
    resp = await client.post(
        "/api/courses",
        json={
            "name": "操作系统",
            "description": "操作系统原理",
            "semester": "2025-2026-1",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # Update the course
    resp = await client.put(
        f"/api/courses/{course_id}",
        json={
            "name": "操作系统原理",
            "description": "操作系统原理与实践",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "操作系统原理"
    assert data["description"] == "操作系统原理与实践"
    assert data["semester"] == "2025-2026-1"  # unchanged
    assert data["teacher_id"] == teacher.id
    assert data["teacher_name"] == "李老师"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_course_other_teacher_forbidden(client, db_session):
    await create_test_user(
        db_session, username="teacher_own", role="teacher", real_name="王老师"
    )
    await create_test_user(
        db_session, username="teacher_other", role="teacher", real_name="赵老师"
    )
    token_own = await login_user(client, "teacher_own")
    token_other = await login_user(client, "teacher_other")

    # teacher_own creates a course
    resp = await client.post(
        "/api/courses",
        json={
            "name": "编译原理",
            "description": "编译器设计",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(token_own),
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # teacher_other tries to update — should be 403
    resp = await client.put(
        f"/api/courses/{course_id}",
        json={"name": "编译原理改"},
        headers=auth_headers(token_other),
    )
    assert resp.status_code == 403
    assert "只能编辑自己的课程" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_update_course_admin_can_edit(client, db_session):
    await create_test_user(
        db_session, username="teacher_for_admin", role="teacher", real_name="孙老师"
    )
    await create_test_user(
        db_session, username="admin_edit", role="admin", real_name="管理员"
    )
    teacher_token = await login_user(client, "teacher_for_admin")
    admin_token = await login_user(client, "admin_edit")

    # Teacher creates a course
    resp = await client.post(
        "/api/courses",
        json={
            "name": "数据库系统",
            "description": "数据库概论",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(teacher_token),
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # Admin updates it — should succeed
    resp = await client.put(
        f"/api/courses/{course_id}",
        json={"description": "数据库系统概论（更新）"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "数据库系统概论（更新）"
    assert data["name"] == "数据库系统"  # unchanged


# --- Task 7: Archive and Delete tests ---


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_course_own(client, db_session):
    await create_test_user(
        db_session, username="teacher_arch1", role="teacher", real_name="归档老师"
    )
    token = await login_user(client, "teacher_arch1")

    # Create a course
    resp = await client.post(
        "/api/courses",
        json={
            "name": "归档测试课程",
            "description": "用于测试归档",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # Archive the course
    resp = await client.post(
        f"/api/courses/{course_id}/archive",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == course_id
    assert data["status"] == "archived"


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_course_other_teacher_forbidden(client, db_session):
    await create_test_user(
        db_session, username="teacher_arch_own", role="teacher", real_name="拥有者"
    )
    await create_test_user(
        db_session, username="teacher_arch_other", role="teacher", real_name="其他人"
    )
    token_own = await login_user(client, "teacher_arch_own")
    token_other = await login_user(client, "teacher_arch_other")

    # teacher_arch_own creates a course
    resp = await client.post(
        "/api/courses",
        json={
            "name": "别人不能归档",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(token_own),
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # teacher_arch_other tries to archive — 403
    resp = await client.post(
        f"/api/courses/{course_id}/archive",
        headers=auth_headers(token_other),
    )
    assert resp.status_code == 403
    assert "无权归档此课程" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_course_not_allowed(client, db_session):
    await create_test_user(
        db_session, username="teacher_del", role="teacher", real_name="删除测试老师"
    )
    token = await login_user(client, "teacher_del")

    # Create a course
    resp = await client.post(
        "/api/courses",
        json={
            "name": "不能删除课程",
            "semester": "2025-2026-2",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # DELETE should return 405
    resp = await client.delete(
        f"/api/courses/{course_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 405
    assert "课程不支持删除，请使用归档" in resp.json()["detail"]
