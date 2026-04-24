import json

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.prompt_template import PromptTemplate
from app.models.task import Task
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_qa_env(db_session):
    teacher = await create_test_user(db_session, username="teacher_qa", role="teacher")
    student = await create_test_user(db_session, username="student_qa", role="student")
    other_student = await create_test_user(db_session, username="student_other_qa", role="student")

    cls = Class(name="Q&A测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student.primary_class_id = cls.id
    await db_session.flush()

    course = Course(
        name="Python程序设计", semester="2025-2026-2",
        teacher_id=teacher.id, description="Python基础与Web开发",
    )
    db_session.add(course)
    await db_session.flush()

    task = Task(
        title="Flask Web开发实践",
        description="使用Flask框架开发一个简单的Web应用",
        requirements="提交完整的源代码和实验报告",
        class_id=cls.id, course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip", ".pdf"]),
    )
    db_session.add(task)
    await db_session.flush()

    template = PromptTemplate(
        name="student_qa",
        description="学生任务问答",
        template_text="根据以下任务信息回答学生的问题。只使用提供的上下文，不要编造信息。\n\n任务：{task_title}\n描述：{task_description}\n要求：{task_requirements}\n课程：{course_name}\n\n学生问题：{question}",
        variables=json.dumps(["task_title", "task_description", "task_requirements", "course_name", "question"]),
    )
    db_session.add(template)
    await db_session.flush()

    return {
        "teacher": teacher, "student": student, "other_student": other_student,
        "cls": cls, "course": course, "task": task,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_success(client, db_session, setup_qa_env):
    env = setup_qa_env
    token = await login_user(client, "student_qa")

    resp = await client.post(
        f"/api/tasks/{env['task'].id}/qa",
        json={"question": "需要提交什么格式？"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
    assert "usage_log_id" in data
    assert isinstance(data["usage_log_id"], int)
    assert "prompt_tokens" in data
    assert "completion_tokens" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_teacher_forbidden(client, db_session, setup_qa_env):
    env = setup_qa_env
    token = await login_user(client, "teacher_qa")

    resp = await client.post(
        f"/api/tasks/{env['task'].id}/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_other_class_student_forbidden(client, db_session, setup_qa_env):
    env = setup_qa_env
    token = await login_user(client, "student_other_qa")

    resp = await client.post(
        f"/api/tasks/{env['task'].id}/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_task_not_found(client, db_session, setup_qa_env):
    token = await login_user(client, "student_qa")

    resp = await client.post(
        "/api/tasks/99999/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_template_missing(client, db_session):
    student = await create_test_user(db_session, username="student_notpl", role="student")
    teacher = await create_test_user(db_session, username="teacher_notpl_qa", role="teacher")
    cls = Class(name="无模板班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()
    student.primary_class_id = cls.id
    await db_session.flush()
    task = Task(
        title="测试任务", class_id=cls.id, created_by=teacher.id,
        deadline="2026-12-31 23:59:59", allowed_file_types=json.dumps([".pdf"]),
    )
    db_session.add(task)
    await db_session.flush()

    token = await login_user(client, "student_notpl")
    resp = await client.post(
        f"/api/tasks/{task.id}/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "问答模板未配置"
