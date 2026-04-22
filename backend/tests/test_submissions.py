import io
import datetime
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.grade import Grade


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_success(client, db_session, upload_dir):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(
        db_session, username="stu1", role="student", primary_class_id=cls.id
    )
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    stu_token = await login_user(client, "stu1")
    upload_resp = await client.post(
        "/api/files/upload",
        files={"file": ("report.pdf", io.BytesIO(b"PDF content"), "application/pdf")},
        headers=auth_headers(stu_token),
    )
    file_token = upload_resp.json()["file_token"]

    resp = await client.post(
        f"/api/tasks/{task.id}/submissions",
        json={"file_tokens": [file_token]},
        headers=auth_headers(stu_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_id"] == task.id
    assert data["student_id"] == student.id
    assert data["version"] == 1
    assert data["is_late"] is False
    assert len(data["files"]) == 1
    assert data["files"][0]["file_name"] == "report.pdf"


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_deadline_passed_reject(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(
        db_session,
        class_id=cls.id,
        created_by=teacher.id,
        deadline=datetime.datetime(2020, 1, 1),
    )

    token = await login_user(client, "stu1")
    resp = await client.post(
        f"/api/tasks/{task.id}/submissions",
        json={"file_tokens": ["fake-token"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "截止" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_submission_own(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "stu1")
    resp = await client.get(f"/api/submissions/{sub.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == sub.id


@pytest.mark.asyncio(loop_scope="session")
async def test_get_submission_grade_visible_only_when_published(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    grade = Grade(submission_id=sub.id, score=85.0, feedback="Good", graded_by=teacher.id)
    db_session.add(grade)
    await db_session.flush()

    token = await login_user(client, "stu1")

    resp = await client.get(f"/api/submissions/{sub.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["grade"] is None

    task.grades_published = True
    await db_session.flush()

    resp = await client.get(f"/api/submissions/{sub.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["grade"]["score"] == 85.0


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_list_submissions(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    s1 = await create_test_user(db_session, username="stu1", role="student", real_name="张三", primary_class_id=cls.id)
    s2 = await create_test_user(db_session, username="stu2", role="student", real_name="李四", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub1 = Submission(task_id=task.id, student_id=s1.id)
    sub2 = Submission(task_id=task.id, student_id=s2.id)
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.get(f"/api/tasks/{task.id}/submissions", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {s["student_name"] for s in data}
    assert names == {"张三", "李四"}
