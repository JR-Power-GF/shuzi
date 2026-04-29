import datetime
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_with_course(client, db_session):
    """Teacher creates task linked to own course"""
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = course_resp.json()["id"]

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "网络实验",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf"],
            "course_id": course_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["course_id"] == course_id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_with_unowned_course(client, db_session):
    """Teacher cannot link task to another teacher's course"""
    teacher1 = await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher1.id)
    token1 = await login_user(client, "teacher1")
    token2 = await login_user(client, "teacher2")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token1),
    )
    course_id = course_resp.json()["id"]

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "网络实验",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf"],
            "course_id": course_id,
        },
        headers=auth_headers(token2),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_without_course(client, db_session):
    """Task without course_id still works (backward compatible)"""
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "无课程任务",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["course_id"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_update_task_course(client, db_session):
    """Teacher can update task to link it to a course"""
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = course_resp.json()["id"]

    task = await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)

    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"course_id": course_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["course_id"] == course_id


@pytest.mark.asyncio(loop_scope="session")
async def test_student_tasks_exclude_archived_course(client, db_session):
    """Student should not see tasks belonging to archived courses"""
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, name="1班", teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    token_t = await login_user(client, "teacher1")
    token_s = await login_user(client, "stu1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "归档课程", "semester": "2025-2026-2"},
        headers=auth_headers(token_t),
    )
    archived_course_id = course_resp.json()["id"]

    task1 = await create_test_task(db_session, title="归档任务", class_id=cls.id, created_by=teacher.id)
    task1.course_id = archived_course_id
    task2 = await create_test_task(db_session, title="普通任务", class_id=cls.id, created_by=teacher.id)
    await db_session.flush()

    await client.post(
        f"/api/courses/{archived_course_id}/archive",
        headers=auth_headers(token_t),
    )

    resp = await client.get("/api/tasks/my", headers=auth_headers(token_s))
    assert resp.status_code == 200
    data = resp.json()
    titles = {t["title"] for t in data}
    assert "归档任务" not in titles
    assert "普通任务" in titles


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_tasks_filter_by_course(client, db_session):
    """Admin can filter tasks by course_id"""
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    admin = await create_test_user(db_session, username="admin1", role="admin")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token_t = await login_user(client, "teacher1")
    token_a = await login_user(client, "admin1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    course_id = course_resp.json()["id"]

    task1 = await create_test_task(db_session, title="课程任务", class_id=cls.id, created_by=teacher.id)
    task1.course_id = course_id
    task2 = await create_test_task(db_session, title="无课程任务", class_id=cls.id, created_by=teacher.id)
    await db_session.flush()

    resp = await client.get(
        f"/api/tasks?course_id={course_id}",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "课程任务"
