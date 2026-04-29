import datetime
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_success(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "网络协议实验报告",
            "description": "完成Wireshark抓包分析",
            "class_id": cls.id,
            "deadline": "2026-06-01T23:59:59",
            "allowed_file_types": [".pdf", ".docx"],
            "max_file_size_mb": 20,
            "allow_late_submission": True,
            "late_penalty_percent": 10.0,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "网络协议实验报告"
    assert data["class_id"] == cls.id
    assert data["created_by"] == teacher.id
    assert data["status"] == "active"
    assert data["grades_published"] is False
    assert data["allowed_file_types"] == [".pdf", ".docx"]
    assert data["allow_late_submission"] is True
    assert data["late_penalty_percent"] == 10.0


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_not_own_class(client, db_session):
    teacher1 = await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher1.id)

    token = await login_user(client, "teacher2")
    resp = await client.post(
        "/api/tasks",
        json={
            "title": "任务",
            "class_id": cls.id,
            "deadline": "2026-06-01T23:59:59",
            "allowed_file_types": [".pdf"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_my_tasks_student(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(
        db_session, username="stu1", role="student", primary_class_id=cls.id
    )
    await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)
    await create_test_task(db_session, title="任务2", class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "stu1")
    resp = await client.get("/api/tasks/my", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {t["title"] for t in data}
    assert titles == {"任务1", "任务2"}


@pytest.mark.asyncio(loop_scope="session")
async def test_get_my_tasks_teacher(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_task(db_session, title="我的任务", class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "teacher1")
    resp = await client.get("/api/tasks/my", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "我的任务"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_task_detail_student_in_class(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, title="网络实验", class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "stu1")
    resp = await client.get(f"/api/tasks/{task.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "网络实验"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_task_detail_forbidden_other_student(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    cls2 = await create_test_class(db_session, name="其他班2")
    await create_test_user(db_session, username="outsider", role="student", primary_class_id=cls2.id)

    token = await login_user(client, "outsider")
    resp = await client.get(f"/api/tasks/{task.id}", headers=auth_headers(token))
    assert resp.status_code == 403
