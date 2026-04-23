"""Tests for OpenSpec verification critical issues (C-1 through C-16)."""
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_login_deactivated_user_returns_403(client, db_session):
    """C-1: Deactivated account should return 403 with '账户已停用', not 401."""
    import bcrypt
    from app.models.user import User

    pw_hash = bcrypt.hashpw(b"pass1234", bcrypt.gensalt()).decode()
    user = User(
        username="deact_403", password_hash=pw_hash,
        real_name="停用用户", role="student", is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "deact_403", "password": "pass1234"},
    )
    assert resp.status_code == 403
    assert "停用" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_login_locked_account_message_spec(client, db_session):
    """C-2: Lockout message should match spec '账户已锁定，请30分钟后重试'."""
    import datetime
    import bcrypt
    from app.models.user import User

    pw_hash = bcrypt.hashpw(b"pass1234", bcrypt.gensalt()).decode()
    user = User(
        username="locked_spec", password_hash=pw_hash,
        real_name="锁定", role="student",
        locked_until=datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "locked_spec", "password": "pass1234"},
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert "锁定" in detail
    assert "30" in detail


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_wrong_current_returns_401(client, db_session):
    """C-4: Wrong current password in change-password should return 401, not 400."""
    from tests.helpers import create_test_user, login_user

    user = await create_test_user(db_session, username="chpw_user", password="pass1234")
    token = await login_user(client, "chpw_user", "pass1234")

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_create_user_duplicate_returns_409(client, db_session):
    """C-5: Duplicate username should return 409, not 400."""
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_409", password="admin1234", role="admin")
    await create_test_user(db_session, username="dup_409", password="pass1234")
    token = await login_user(client, "admin_409", "admin1234")

    resp = await client.post(
        "/api/users",
        json={"username": "dup_409", "password": "pass1234", "real_name": "重复", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_cannot_deactivate_self(client, db_session):
    """C-6: Admin should not be able to deactivate their own account."""
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_self", password="admin1234", role="admin")
    token = await login_user(client, "admin_self", "admin1234")

    resp = await client.put(
        f"/api/users/{admin.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "自己" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_can_change_user_role(client, db_session):
    """C-7: Admin should be able to change a user's role."""
    from tests.helpers import create_test_user, login_user

    admin = await create_test_user(db_session, username="admin_role", password="admin1234", role="admin")
    target = await create_test_user(db_session, username="role_target", password="pass1234", role="student")
    token = await login_user(client, "admin_role", "admin1234")

    resp = await client.put(
        f"/api/users/{target.id}",
        json={"role": "teacher"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "teacher"


@pytest.mark.asyncio(loop_scope="session")
async def test_task_edit_rejects_file_type_change_after_submission(client, db_session):
    """C-9: Cannot change allowed_file_types after submissions exist."""
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="edit_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="edit_student", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "edit_teacher", "pass1234")
    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"allowed_file_types": [".txt"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "文件类型" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_task_edit_rejects_deadline_reduction_before_earliest_submission(client, db_session):
    """C-9: Cannot reduce deadline before earliest submission timestamp."""
    import datetime
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="dl_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="dl_student", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(
        db_session, class_id=cls.id, created_by=teacher.id,
        deadline=datetime.datetime(2026, 12, 31, 23, 59, 59),
    )

    from app.models.submission import Submission
    sub = Submission(
        task_id=task.id, student_id=student.id,
        submitted_at=datetime.datetime(2026, 6, 15, 12, 0, 0),
    )
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "dl_teacher", "pass1234")
    # Try to set deadline before the earliest submission
    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"deadline": "2026-06-01T23:59:59"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "截止日期" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_grade_rejected_when_grades_published(client, db_session):
    """C-14: Cannot grade while grades_published=true."""
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="pub_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="pub_student", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)

    task.grades_published = True
    await db_session.flush()

    token = await login_user(client, "pub_teacher", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 80},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "发布" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_grade_rejected_when_grades_published(client, db_session):
    """C-15: Cannot bulk grade while grades_published=true."""
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="bp_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="bp_student", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)

    task.grades_published = True
    await db_session.flush()

    token = await login_user(client, "bp_teacher", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/bulk",
        json={"grades": [{"submission_id": sub.id, "score": 80}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "发布" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_grades_rejected_when_no_grades_exist(client, db_session):
    """C-16: Cannot publish grades when no grades exist for the task."""
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="nopub_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "nopub_teacher", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "成绩" in resp.json()["detail"]
