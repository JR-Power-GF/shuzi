import io
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_minimum_closed_loop(client, db_session, upload_dir):
    # --- Setup: admin creates class, assigns teacher ---
    admin = await create_test_user(db_session, username="admin", password="admin123", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher1", password="teacher123", role="teacher", real_name="王老师")
    student = await create_test_user(db_session, username="student1", password="student123", role="student", real_name="张三")

    admin_token = await login_user(client, "admin", "admin123")
    cls_resp = await client.post(
        "/api/classes",
        json={"name": "计算机网络1班", "semester": "2025-2026-2", "teacher_id": teacher.id},
        headers=auth_headers(admin_token),
    )
    assert cls_resp.status_code == 201
    class_id = cls_resp.json()["id"]

    student.primary_class_id = class_id
    await db_session.flush()

    # --- Step 1: Teacher creates a task ---
    teacher_token = await login_user(client, "teacher1", "teacher123")
    task_resp = await client.post(
        "/api/tasks",
        json={
            "title": "Wireshark抓包实验",
            "description": "完成三次握手抓包分析",
            "class_id": class_id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf", ".docx"],
            "max_file_size_mb": 20,
            "allow_late_submission": True,
            "late_penalty_percent": 10.0,
        },
        headers=auth_headers(teacher_token),
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]
    assert task_resp.json()["title"] == "Wireshark抓包实验"

    # --- Step 2: Student views available tasks ---
    student_token = await login_user(client, "student1", "student123")
    my_tasks_resp = await client.get("/api/tasks/my", headers=auth_headers(student_token))
    assert my_tasks_resp.status_code == 200
    assert len(my_tasks_resp.json()) == 1
    assert my_tasks_resp.json()[0]["id"] == task_id

    # --- Step 3: Student uploads a file ---
    upload_resp = await client.post(
        "/api/files/upload",
        files={"file": ("report.pdf", io.BytesIO(b"PDF report content"), "application/pdf")},
        headers=auth_headers(student_token),
    )
    assert upload_resp.status_code == 200
    file_token = upload_resp.json()["file_token"]
    assert file_token

    # --- Step 4: Student submits ---
    submit_resp = await client.post(
        f"/api/tasks/{task_id}/submissions",
        json={"file_tokens": [file_token]},
        headers=auth_headers(student_token),
    )
    assert submit_resp.status_code == 201
    submission_id = submit_resp.json()["id"]
    assert submit_resp.json()["version"] == 1
    assert submit_resp.json()["is_late"] is False
    assert len(submit_resp.json()["files"]) == 1

    # --- Step 5: Teacher views submissions ---
    subs_resp = await client.get(
        f"/api/tasks/{task_id}/submissions",
        headers=auth_headers(teacher_token),
    )
    assert subs_resp.status_code == 200
    assert len(subs_resp.json()) == 1
    assert subs_resp.json()[0]["student_name"] == "张三"
    assert subs_resp.json()[0]["grade"] is None

    # --- Step 6: Teacher grades ---
    grade_resp = await client.post(
        f"/api/tasks/{task_id}/grades",
        json={"submission_id": submission_id, "score": 92.0, "feedback": "分析很详细，继续保持"},
        headers=auth_headers(teacher_token),
    )
    assert grade_resp.status_code == 200
    assert grade_resp.json()["score"] == 92.0

    # --- Step 7: Student cannot see grade yet (not published) ---
    sub_detail_resp = await client.get(
        f"/api/submissions/{submission_id}",
        headers=auth_headers(student_token),
    )
    assert sub_detail_resp.status_code == 200
    assert sub_detail_resp.json()["grade"] is None

    # --- Step 8: Teacher publishes grades ---
    publish_resp = await client.post(
        f"/api/tasks/{task_id}/grades/publish",
        headers=auth_headers(teacher_token),
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["grades_published"] is True

    # --- Step 9: Student sees the grade ---
    final_resp = await client.get(
        f"/api/submissions/{submission_id}",
        headers=auth_headers(student_token),
    )
    assert final_resp.status_code == 200
    grade_data = final_resp.json()["grade"]
    assert grade_data is not None
    assert grade_data["score"] == 92.0
    assert grade_data["feedback"] == "分析很详细，继续保持"
