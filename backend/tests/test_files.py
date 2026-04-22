import io
import os
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_file_success(client, db_session, upload_dir):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    file_content = b"Test PDF content for upload"
    resp = await client.post(
        "/api/files/upload",
        files={"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_token"]
    assert data["file_name"] == "report.pdf"
    assert data["file_size"] == len(file_content)
    assert data["file_type"] == ".pdf"


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_file_rejected_type(client, db_session, upload_dir):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.post(
        "/api/files/upload",
        files={"file": ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_download_file_success(client, db_session, upload_dir):
    from app.models.submission import Submission
    from app.models.submission_file import SubmissionFile

    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    student = await create_test_user(db_session, username="stu1", role="student")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student.primary_class_id = cls.id
    await db_session.flush()

    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    file_path = os.path.join(upload_dir, "test_report.pdf")
    with open(file_path, "wb") as f:
        f.write(b"PDF content here")

    sf = SubmissionFile(
        submission_id=sub.id,
        file_name="report.pdf",
        file_path=file_path,
        file_size=14,
        file_type=".pdf",
    )
    db_session.add(sf)
    await db_session.flush()

    token = await login_user(client, "stu1")
    resp = await client.get(f"/api/files/{sf.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.content == b"PDF content here"
