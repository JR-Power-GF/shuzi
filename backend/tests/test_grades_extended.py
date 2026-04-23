import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_grade(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="bulk_teacher", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    s1 = await create_test_user(db_session, username="bulk_s1", password="pass1234", primary_class_id=cls.id)
    s2 = await create_test_user(db_session, username="bulk_s2", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub1 = Submission(task_id=task.id, student_id=s1.id)
    sub2 = Submission(task_id=task.id, student_id=s2.id)
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    token = await login_user(client, "bulk_teacher", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/bulk",
        json={
            "grades": [
                {"submission_id": sub1.id, "score": 85},
                {"submission_id": sub2.id, "score": 90, "feedback": "做得好"},
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["graded_count"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_grade_invalid_score(client, db_session):
    from tests.helpers import create_test_user, create_test_class, create_test_task, login_user

    teacher = await create_test_user(db_session, username="bulk_teacher2", password="pass1234", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="bulk_s3", password="pass1234", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    from app.models.submission import Submission
    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "bulk_teacher2", "pass1234")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/bulk",
        json={"grades": [{"submission_id": sub.id, "score": 150}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
