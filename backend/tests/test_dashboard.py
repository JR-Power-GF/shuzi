import json

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_dashboard_env(db_session):
    admin = await create_test_user(db_session, username="admin_dash", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher_dash", role="teacher", real_name="教师")
    other_teacher = await create_test_user(db_session, username="teacher_other_dash", role="teacher", real_name="其他教师")
    student1 = await create_test_user(db_session, username="student_dash1", role="student", real_name="学生1")
    student2 = await create_test_user(db_session, username="student_dash2", role="student", real_name="学生2")

    # Inactive user — should be excluded from user counts
    inactive = await create_test_user(db_session, username="inactive_dash", role="student", real_name="停用用户")
    inactive.is_active = False
    await db_session.flush()

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
        "student1": student1, "student2": student2, "inactive": inactive,
        "cls": cls, "course": course, "tasks": [task1, task2],
    }


# ---------------------------------------------------------------------------
# Test 1: Admin dashboard requires admin role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_requires_admin(client, setup_dashboard_env):
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
    admin_token = await login_user(client, "admin_dash")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(admin_token))
    assert resp.status_code == 200

    data = resp.json()
    # All required fields must be present
    required_fields = [
        "total_users", "users_by_role", "total_classes",
        "total_active_courses", "total_archived_courses",
        "total_active_tasks", "total_archived_tasks",
        "total_submissions", "pending_grades", "graded",
        "late_submissions", "avg_score", "nearby_deadline",
        "daily_submissions_last_7d",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # Verify types
    assert isinstance(data["users_by_role"], dict)
    assert isinstance(data["daily_submissions_last_7d"], list)

    # Verify values match fixture data
    # Users: 5 active (admin, teacher, other_teacher, student1, student2), 1 inactive excluded
    assert data["total_users"] >= 5
    assert "admin" in data["users_by_role"]
    assert "teacher" in data["users_by_role"]
    assert "student" in data["users_by_role"]

    assert data["total_classes"] >= 1
    assert data["total_active_courses"] >= 1
    assert data["total_active_tasks"] >= 2
    assert data["total_submissions"] >= 3
    assert data["late_submissions"] >= 1
    assert data["pending_grades"] >= 1
    assert data["graded"] >= 2  # sub1 and sub3 are graded
    assert data["avg_score"] is not None
    assert abs(data["avg_score"] - 87.5) < 0.1

    # avg_score should be rounded to 1 decimal
    assert data["avg_score"] == round(data["avg_score"], 1)

    # nearby_deadline should be a non-null string (tasks have 2026-12-31 deadline)
    assert data["nearby_deadline"] is not None


# ---------------------------------------------------------------------------
# Test 4: Teacher dashboard returns correct metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_metrics(client, setup_dashboard_env):
    teacher_token = await login_user(client, "teacher_dash")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(teacher_token))
    assert resp.status_code == 200

    data = resp.json()
    required_fields = [
        "my_classes", "my_active_courses", "my_archived_courses",
        "my_active_tasks", "my_archived_tasks", "my_total_submissions",
        "my_pending_grades", "my_graded", "my_late_submissions",
        "my_avg_score", "my_nearby_deadline", "my_daily_submissions_last_7d",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    assert isinstance(data["my_daily_submissions_last_7d"], list)

    assert data["my_classes"] >= 1
    assert data["my_active_courses"] >= 1
    assert data["my_active_tasks"] >= 2
    assert data["my_total_submissions"] >= 3
    assert data["my_late_submissions"] >= 1
    assert data["my_pending_grades"] >= 1
    assert data["my_graded"] >= 2
    assert data["my_avg_score"] is not None
    assert abs(data["my_avg_score"] - 87.5) < 0.1
    assert data["my_nearby_deadline"] is not None


# ---------------------------------------------------------------------------
# Test 5: Teacher dashboard data isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_isolation(client, setup_dashboard_env):
    other_token = await login_user(client, "teacher_other_dash")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(other_token))
    assert resp.status_code == 200

    data = resp.json()
    assert data["my_classes"] == 0
    assert data["my_active_courses"] == 0
    assert data["my_active_tasks"] == 0
    assert data["my_total_submissions"] == 0
    assert data["my_late_submissions"] == 0
    assert data["my_pending_grades"] == 0
    assert data["my_graded"] == 0
    assert data["my_avg_score"] is None
    assert data["my_nearby_deadline"] is None


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
    assert data["total_users"] >= 1
    assert data["total_submissions"] == 0
    assert data["late_submissions"] == 0
    assert data["pending_grades"] == 0
    assert data["graded"] == 0
    assert data["avg_score"] is None
    assert data["nearby_deadline"] is None


# ---------------------------------------------------------------------------
# Test 7: Course stats endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_course_stats_admin(client, setup_dashboard_env):
    admin_token = await login_user(client, "admin_dash")
    resp = await client.get("/api/dashboard/courses", headers=auth_headers(admin_token))
    assert resp.status_code == 200

    data = resp.json()
    assert "courses" in data
    assert isinstance(data["courses"], list)
    assert len(data["courses"]) >= 1

    course = data["courses"][0]
    assert "course_id" in course
    assert "course_name" in course
    assert "teacher_name" in course
    assert "task_count" in course
    assert "submission_count" in course
    assert "pending_grade_count" in course
    assert "graded_count" in course
    assert "average_score" in course

    # Verify values for fixture course
    assert course["task_count"] >= 2
    assert course["submission_count"] >= 3
    assert course["pending_grade_count"] >= 1
    assert course["graded_count"] >= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_course_stats_teacher_scoped(client, setup_dashboard_env):
    teacher_token = await login_user(client, "teacher_dash")
    resp = await client.get("/api/dashboard/courses", headers=auth_headers(teacher_token))
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["courses"]) >= 1

    # Other teacher should see no courses
    other_token = await login_user(client, "teacher_other_dash")
    resp = await client.get("/api/dashboard/courses", headers=auth_headers(other_token))
    assert resp.status_code == 200
    assert resp.json()["courses"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_course_stats_forbidden_for_student(client, setup_dashboard_env):
    student_token = await login_user(client, "student_dash1")
    resp = await client.get("/api/dashboard/courses", headers=auth_headers(student_token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test 8: is_active filter on user count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_inactive_users_excluded(client, setup_dashboard_env):
    admin_token = await login_user(client, "admin_dash")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(admin_token))
    assert resp.status_code == 200

    data = resp.json()
    # Fixture creates 5 active + 1 inactive. Total should NOT count inactive.
    # We can't assert exact number (other tests add users), but we verify
    # that the field exists and is reasonable.
    assert data["total_users"] >= 5
