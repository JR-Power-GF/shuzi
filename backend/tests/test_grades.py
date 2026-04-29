import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)
from app.models.submission import Submission
from app.models.grade import Grade
from app.models.task import Task
from sqlalchemy import select


@pytest.mark.asyncio(loop_scope="session")
async def test_grade_submission(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 85.0, "feedback": "Good work"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 85.0
    assert data["feedback"] == "Good work"
    assert data["submission_id"] == sub.id
    assert data["penalty_applied"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_grade_late_submission_auto_penalty(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(
        db_session, class_id=cls.id, created_by=teacher.id,
        allow_late_submission=True, late_penalty_percent=20.0,
    )

    sub = Submission(task_id=task.id, student_id=student.id, is_late=True)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 80.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 80.0
    assert data["penalty_applied"] == 16.0  # 80 * 20%


@pytest.mark.asyncio(loop_scope="session")
async def test_grade_invalid_score(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 150.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_grades(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    grade = Grade(submission_id=sub.id, score=90.0, graded_by=teacher.id)
    db_session.add(grade)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/publish",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["grades_published"] is True

    await db_session.flush()
    result = await db_session.execute(select(Task).where(Task.id == task.id))
    refreshed = result.scalar_one()
    assert refreshed.grades_published is True


@pytest.mark.asyncio(loop_scope="session")
async def test_unpublish_grades(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    task.grades_published = True
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/unpublish",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["grades_published"] is False
