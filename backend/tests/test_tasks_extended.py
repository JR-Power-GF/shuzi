import pytest
import json
import datetime


@pytest.mark.asyncio(loop_scope="session")
async def test_update_task(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="upd_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id, title="旧标题")
    token = await login_user(client, "upd_teacher", "pass1234")

    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"title": "新标题", "description": "新描述"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_task_not_owner(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    owner = await create_test_user(db_session, username="task_owner", password="pass1234", role="teacher")
    other = await create_test_user(db_session, username="task_other", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=owner.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=owner.id)
    token = await login_user(client, "task_other", "pass1234")

    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"title": "被改了"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_task_no_submissions(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="del_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    token = await login_user(client, "del_teacher", "pass1234")

    resp = await client.delete(
        f"/api/tasks/{task.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_task_with_submissions(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="del_teacher2", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="del_student", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    # Create a submission directly
    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "del_teacher2", "pass1234")
    resp = await client.delete(
        f"/api/tasks/{task.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_task(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="arch_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    token = await login_user(client, "arch_teacher", "pass1234")

    resp = await client.post(
        f"/api/tasks/{task.id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_tasks_admin(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    admin = await create_test_user(db_session, username="admin_tasklist", password="admin1234", role="admin")
    teacher = await create_test_user(db_session, username="list_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_task(db_session, class_id=cls.id, created_by=teacher.id, title="任务1")
    await create_test_task(db_session, class_id=cls.id, created_by=teacher.id, title="任务2")
    token = await login_user(client, "admin_tasklist", "admin1234")

    resp = await client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_can_create_task(client, db_session):
    """FAIL-003 fix: admin should be able to create tasks for any class."""
    from tests.helpers import create_test_user, create_test_class, login_user

    admin = await create_test_user(
        db_session, username="admin_taskcreate", password="admin1234", role="admin"
    )
    teacher = await create_test_user(
        db_session, username="tc_teacher", password="pass1234", role="teacher"
    )
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "admin_taskcreate", "admin1234")

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "管理员创建的任务",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf", ".doc"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "管理员创建的任务"


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_can_archive_task(client, db_session):
    """FAIL-003 fix: admin should be able to archive tasks."""
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    admin = await create_test_user(
        db_session, username="admin_archive", password="admin1234", role="admin"
    )
    teacher = await create_test_user(
        db_session, username="ar_teacher", password="pass1234", role="teacher"
    )
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    token = await login_user(client, "admin_archive", "admin1234")

    resp = await client.post(
        f"/api/tasks/{task.id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
