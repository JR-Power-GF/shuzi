import json

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_dashboard_env(db_session):
    admin = await create_test_user(db_session, username="admin_dash", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher_dash", role="teacher", real_name="教师")
    other_teacher = await create_test_user(db_session, username="teacher_other_dash", role="teacher", real_name="其他教师")
    student1 = await create_test_user(db_session, username="student_dash1", role="student", real_name="学生1")
    student2 = await create_test_user(db_session, username="student_dash2", role="student", real_name="学生2")

    cls = Class(name="统计测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student1.primary_class_id = cls.id
    student2.primary_class_id = cls.id
    await db_session.flush()

    course = Course(
        name="统计测试课程", semester="2025-2026-2",
        teacher_id=teacher.id, description="用于统计测试",
    )
    db_session.add(course)
    await db_session.flush()

    task1 = Task(
        title="统计任务1", class_id=cls.id, course_id=course.id,
        created_by=teacher.id, deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".pdf"]),
    )
    task2 = Task(
        title="统计任务2", class_id=cls.id, course_id=course.id,
        created_by=teacher.id, deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".pdf"]),
    )
    db_session.add_all([task1, task2])
    await db_session.flush()

    # task1: student1 submitted on time, graded
    sub1 = Submission(task_id=task1.id, student_id=student1.id, version=1, is_late=False)
    db_session.add(sub1)
    await db_session.flush()
    grade1 = Grade(submission_id=sub1.id, score=85.0, graded_by=teacher.id)
    db_session.add(grade1)

    # task1: student2 submitted late, not graded
    sub2 = Submission(task_id=task1.id, student_id=student2.id, version=1, is_late=True)
    db_session.add(sub2)

    # task2: student1 submitted on time, graded
    sub3 = Submission(task_id=task2.id, student_id=student1.id, version=1, is_late=False)
    db_session.add(sub3)
    await db_session.flush()
    grade2 = Grade(submission_id=sub3.id, score=90.0, graded_by=teacher.id)
    db_session.add(grade2)

    await db_session.flush()

    return {
        "admin": admin, "teacher": teacher, "other_teacher": other_teacher,
        "student1": student1, "student2": student2,
        "cls": cls, "course": course, "tasks": [task1, task2],
    }


# ---------------------------------------------------------------------------
# Test 1: Admin dashboard requires admin role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_requires_admin(client, setup_dashboard_env):
    env = setup_dashboard_env

    # Teacher → 403
    teacher_token = await login_user(client, "teacher_dash")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(teacher_token))
    assert resp.status_code == 403

    # Student → 403
    student_token = await login_user(client, "student_dash1")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(student_token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test 2: Teacher dashboard requires teacher role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_requires_teacher(client, setup_dashboard_env):
    env = setup_dashboard_env

    # Admin → 403
    admin_token = await login_user(client, "admin_dash")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(admin_token))
    assert resp.status_code == 403

    # Student → 403
    student_token = await login_user(client, "student_dash1")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(student_token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test 3: Admin dashboard returns correct metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_metrics(client, setup_dashboard_env):
    env = setup_dashboard_env

    admin_token = await login_user(client, "admin_dash")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(admin_token))
    assert resp.status_code == 200

    data = resp.json()
    # All required fields must be present
    assert "total_users" in data
    assert "users_by_role" in data
    assert "total_active_courses" in data
    assert "total_active_tasks" in data
    assert "total_submissions" in data
    assert "late_submissions" in data
    assert "pending_grades" in data
    assert "avg_score" in data
    assert "daily_submissions_last_7d" in data

    # Verify types
    assert isinstance(data["total_users"], int)
    assert isinstance(data["users_by_role"], dict)
    assert isinstance(data["total_active_courses"], int)
    assert isinstance(data["total_active_tasks"], int)
    assert isinstance(data["total_submissions"], int)
    assert isinstance(data["late_submissions"], int)
    assert isinstance(data["pending_grades"], int)
    assert isinstance(data["daily_submissions_last_7d"], list)


# ---------------------------------------------------------------------------
# Test 4: Teacher dashboard returns correct metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_metrics(client, setup_dashboard_env):
    env = setup_dashboard_env

    teacher_token = await login_user(client, "teacher_dash")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(teacher_token))
    assert resp.status_code == 200

    data = resp.json()
    # All required fields must be present
    assert "my_active_courses" in data
    assert "my_active_tasks" in data
    assert "my_total_submissions" in data
    assert "my_late_submissions" in data
    assert "my_pending_grades" in data
    assert "my_avg_score" in data
    assert "my_daily_submissions_last_7d" in data

    # Verify types
    assert isinstance(data["my_active_courses"], int)
    assert isinstance(data["my_active_tasks"], int)
    assert isinstance(data["my_total_submissions"], int)
    assert isinstance(data["my_late_submissions"], int)
    assert isinstance(data["my_pending_grades"], int)
    assert isinstance(data["my_daily_submissions_last_7d"], list)


# ---------------------------------------------------------------------------
# Test 5: Teacher dashboard data isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_isolation(client, setup_dashboard_env):
    env = setup_dashboard_env

    other_token = await login_user(client, "teacher_other_dash")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(other_token))
    assert resp.status_code == 200

    data = resp.json()
    # Other teacher should see zeros for all counts
    assert data["my_active_courses"] == 0
    assert data["my_active_tasks"] == 0
    assert data["my_total_submissions"] == 0
    assert data["my_late_submissions"] == 0
    assert data["my_pending_grades"] == 0
    assert data["my_avg_score"] is None


# ---------------------------------------------------------------------------
# Test 6: Admin dashboard works with empty system
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_empty_system(client, db_session):
    admin = await create_test_user(db_session, username="admin_empty_dash", role="admin", real_name="空系统管理员")

    admin_token = await login_user(client, "admin_empty_dash")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(admin_token))
    assert resp.status_code == 200

    data = resp.json()
    assert data["total_users"] >= 1  # at least the admin
    assert data["total_submissions"] == 0
    assert data["late_submissions"] == 0
    assert data["pending_grades"] == 0
    assert data["avg_score"] is None
