import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.prompt_template import PromptTemplate
from app.models.submission import Submission
from app.models.task import Task
from app.services.ai import AIServiceError, BudgetExceededError
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_summary_env(db_session):
    """Create the full environment for training summary tests.

    Users:
      - teacher: owns the class and course
      - student: enrolled in the class, has submissions
      - other_student: in the SAME class, also has submissions (permission boundary)
      - another_student: in a DIFFERENT class (cross-class isolation)
    """
    teacher = await create_test_user(
        db_session, username="teacher_summary", role="teacher"
    )
    student = await create_test_user(
        db_session, username="student_summary", role="student"
    )
    other_student = await create_test_user(
        db_session, username="student_other_summary", role="student"
    )
    another_student = await create_test_user(
        db_session, username="student_another_summary", role="student"
    )

    # Class that student + other_student belong to
    cls = Class(name="Summary测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student.primary_class_id = cls.id
    other_student.primary_class_id = cls.id
    await db_session.flush()

    # Different class for another_student
    other_cls = Class(
        name="Summary其他班", semester="2025-2026-2", teacher_id=teacher.id
    )
    db_session.add(other_cls)
    await db_session.flush()

    another_student.primary_class_id = other_cls.id
    await db_session.flush()

    # Course
    course = Course(
        name="Python程序设计-Summary",
        semester="2025-2026-2",
        teacher_id=teacher.id,
        description="用于训练总结测试的课程",
    )
    db_session.add(course)
    await db_session.flush()

    # Two tasks for the course in the main class
    task1 = Task(
        title="任务一：Flask基础",
        description="Flask入门实践",
        requirements="提交源代码",
        class_id=cls.id,
        course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip", ".pdf"]),
    )
    db_session.add(task1)
    await db_session.flush()

    task2 = Task(
        title="任务二：数据库集成",
        description="SQLAlchemy ORM使用",
        requirements="提交代码和报告",
        class_id=cls.id,
        course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip", ".pdf"]),
    )
    db_session.add(task2)
    await db_session.flush()

    # Submissions for student (the requesting student)
    sub1 = Submission(
        task_id=task1.id,
        student_id=student.id,
        version=1,
        is_late=False,
    )
    db_session.add(sub1)
    await db_session.flush()

    sub2 = Submission(
        task_id=task2.id,
        student_id=student.id,
        version=1,
        is_late=False,
    )
    db_session.add(sub2)
    await db_session.flush()

    # Submissions for other_student (same class — the permission boundary)
    other_sub1 = Submission(
        task_id=task1.id,
        student_id=other_student.id,
        version=1,
        is_late=False,
    )
    db_session.add(other_sub1)
    await db_session.flush()

    other_sub2 = Submission(
        task_id=task2.id,
        student_id=other_student.id,
        version=1,
        is_late=True,
    )
    db_session.add(other_sub2)
    await db_session.flush()

    # PromptTemplate for training_summary
    template = PromptTemplate(
        name="training_summary",
        description="训练总结生成",
        template_text="根据以下学生提交信息生成训练总结。\n\n{submissions_context}",
        variables=json.dumps(["submissions_context"]),
    )
    db_session.add(template)
    await db_session.flush()

    return {
        "teacher": teacher,
        "student": student,
        "other_student": other_student,
        "another_student": another_student,
        "cls": cls,
        "other_cls": other_cls,
        "course": course,
        "task1": task1,
        "task2": task2,
        "sub1": sub1,
        "sub2": sub2,
        "other_sub1": other_sub1,
        "other_sub2": other_sub2,
        "template": template,
    }


# ---------------------------------------------------------------------------
# Test 1: THE CRITICAL PERMISSION TEST
# "只能读取本人提交内容" — can ONLY read own submissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_only_own_submissions(
    client, db_session, setup_summary_env
):
    """Security boundary: prompt sent to AI must contain ONLY the requesting
    student's submissions, never other students' data — even if they share
    the same class."""
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    captured_prompt: list[str] = []

    async def capture_generate(*, db, prompt, user_id, role, endpoint):
        captured_prompt.append(prompt)
        return {
            "text": "AI generated summary",
            "usage_log_id": 1,
            "prompt_tokens": 10,
            "completion_tokens": 10,
        }

    mock_service = AsyncMock()
    mock_service.generate = capture_generate

    with patch(
        "app.routers.courses.get_ai_service", return_value=mock_service
    ):
        resp = await client.post(
            f"/api/courses/{env['course'].id}/generate-summary",
            headers=auth_headers(token),
        )

    # Endpoint should succeed
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    # The prompt MUST have been captured
    assert len(captured_prompt) == 1, "Expected exactly one AI generate call"

    prompt_text = captured_prompt[0]

    # CRITICAL: prompt must contain ONLY the requesting student's 2 submissions.
    # If other_student's data leaked in, we'd see 4 entries and a "迟交" marker
    # (other_student's sub2 is late, but the requesting student's submissions are not).
    submission_entry_count = prompt_text.count("已提交")
    assert (
        submission_entry_count == 2
    ), f"Expected exactly 2 submission entries (student's own), got {submission_entry_count}. Prompt: {prompt_text}"

    # other_student's sub2 is_late=True — this marker must NOT appear in the prompt
    assert (
        "迟交" not in prompt_text
    ), f"Security: prompt contains other_student's late marker. Prompt: {prompt_text}"

    # The prompt SHOULD reference the requesting student's tasks
    assert (
        env["task1"].title in prompt_text
    ), f"Expected task1 title in prompt. Prompt: {prompt_text}"
    assert (
        env["task2"].title in prompt_text
    ), f"Expected task2 title in prompt. Prompt: {prompt_text}"


# ---------------------------------------------------------------------------
# Test 2: Normal success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_success(client, db_session, setup_summary_env):
    """Happy path: student generates summary, gets 200 with all expected fields."""
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "content" in data
    assert len(data["content"]) > 0
    assert "usage_log_id" in data
    assert isinstance(data["usage_log_id"], int)
    assert "prompt_tokens" in data
    assert "completion_tokens" in data


# ---------------------------------------------------------------------------
# Test 3: Teacher forbidden
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_teacher_forbidden(
    client, db_session, setup_summary_env
):
    """Teachers must not be able to generate training summaries."""
    env = setup_summary_env
    token = await login_user(client, "teacher_summary")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Test 4: Student from different class forbidden
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_other_class_forbidden(
    client, db_session, setup_summary_env
):
    """A student who is not enrolled in the course's class cannot generate summary."""
    env = setup_summary_env
    token = await login_user(client, "student_another_summary")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Test 5: No auto-save — generate does NOT persist the summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_no_auto_submit(
    client, db_session, setup_summary_env
):
    """After generating a summary, GET /api/courses/{id}/summary must return 404.
    The generate endpoint must NOT automatically save/submit the summary."""
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    # Generate summary
    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200

    # Verify it was NOT auto-saved
    resp_get = await client.get(
        f"/api/courses/{env['course'].id}/summary",
        headers=auth_headers(token),
    )
    assert (
        resp_get.status_code == 404
    ), f"Expected 404 (no auto-save), got {resp_get.status_code}: {resp_get.text}"


# ---------------------------------------------------------------------------
# Test 6: Course not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_course_not_found(
    client, db_session, setup_summary_env
):
    """Requesting summary for a non-existent course returns 404."""
    token = await login_user(client, "student_summary")

    resp = await client.post(
        "/api/courses/99999/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Error boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_budget_exceeded(
    client, db_session, setup_summary_env
):
    """BudgetExceededError from AI service must produce 429."""
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    mock_service = AsyncMock()
    mock_service.generate.side_effect = BudgetExceededError("额度用完")

    with patch("app.routers.courses.get_ai_service", return_value=mock_service):
        resp = await client.post(
            f"/api/courses/{env['course'].id}/generate-summary",
            headers=auth_headers(token),
        )
    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_ai_error(client, db_session, setup_summary_env):
    """AIServiceError from AI service must produce 502."""
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    mock_service = AsyncMock()
    mock_service.generate.side_effect = AIServiceError("不可用")

    with patch("app.routers.courses.get_ai_service", return_value=mock_service):
        resp = await client.post(
            f"/api/courses/{env['course'].id}/generate-summary",
            headers=auth_headers(token),
        )
    assert resp.status_code == 502, f"Expected 502, got {resp.status_code}: {resp.text}"


@pytest_asyncio.fixture(loop_scope="session")
async def setup_no_submissions_env(db_session):
    """Environment with teacher, student, class, course, task, and template
    but NO submissions for the student."""
    teacher = await create_test_user(
        db_session, username="teacher_nosub", role="teacher"
    )
    student = await create_test_user(
        db_session, username="student_nosub", role="student"
    )

    cls = Class(name="NoSub测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student.primary_class_id = cls.id
    await db_session.flush()

    course = Course(
        name="Python程序设计-NoSub",
        semester="2025-2026-2",
        teacher_id=teacher.id,
        description="无提交测试课程",
    )
    db_session.add(course)
    await db_session.flush()

    task = Task(
        title="任务：无提交测试",
        description="无提交",
        requirements="提交代码",
        class_id=cls.id,
        course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip"]),
    )
    db_session.add(task)
    await db_session.flush()

    template = PromptTemplate(
        name="training_summary",
        description="训练总结生成",
        template_text="根据以下学生提交信息生成训练总结。\n\n{submissions_context}",
        variables=json.dumps(["submissions_context"]),
    )
    db_session.add(template)
    await db_session.flush()

    return {
        "teacher": teacher,
        "student": student,
        "cls": cls,
        "course": course,
        "task": task,
        "template": template,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_no_submissions(
    client, db_session, setup_no_submissions_env
):
    """Student with no submissions gets 400 with '提交' in detail."""
    env = setup_no_submissions_env
    token = await login_user(client, "student_nosub")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "提交" in resp.json()["detail"]


@pytest_asyncio.fixture(loop_scope="session")
async def setup_no_template_env(db_session):
    """Environment with teacher, student, class, course, task, submission
    but NO training_summary PromptTemplate."""
    teacher = await create_test_user(
        db_session, username="teacher_notmpl", role="teacher"
    )
    student = await create_test_user(
        db_session, username="student_notmpl", role="student"
    )

    cls = Class(name="NoTmpl测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student.primary_class_id = cls.id
    await db_session.flush()

    course = Course(
        name="Python程序设计-NoTmpl",
        semester="2025-2026-2",
        teacher_id=teacher.id,
        description="无模板测试课程",
    )
    db_session.add(course)
    await db_session.flush()

    task = Task(
        title="任务：无模板测试",
        description="无模板",
        requirements="提交代码",
        class_id=cls.id,
        course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip"]),
    )
    db_session.add(task)
    await db_session.flush()

    submission = Submission(
        task_id=task.id,
        student_id=student.id,
        version=1,
        is_late=False,
    )
    db_session.add(submission)
    await db_session.flush()

    # Deliberately do NOT create a PromptTemplate for "training_summary"

    return {
        "teacher": teacher,
        "student": student,
        "cls": cls,
        "course": course,
        "task": task,
        "submission": submission,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_template_missing(
    client, db_session, setup_no_template_env
):
    """Missing training_summary template produces 500 with '模板' in detail."""
    env = setup_no_template_env
    token = await login_user(client, "student_notmpl")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 500, f"Expected 500, got {resp.status_code}: {resp.text}"
    assert "模板" in resp.json()["detail"]
