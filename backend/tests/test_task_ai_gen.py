import json

import pytest
import pytest_asyncio

from app.models.prompt_template import PromptTemplate
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_template(db_session):
    template = PromptTemplate(
        name="task_description",
        description="生成任务描述",
        template_text="请为 {course_name} 课程生成一个关于 {topic} 的任务描述。语言：{language}",
        variables=json.dumps(["course_name", "topic", "language"]),
    )
    db_session.add(template)
    await db_session.flush()


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_description_success(client, db_session, setup_template):
    teacher = await create_test_user(db_session, username="teacher_ai_gen", role="teacher")
    token = await login_user(client, "teacher_ai_gen")

    resp = await client.post(
        "/api/tasks/generate-description",
        json={"title": "Python Web 开发", "course_name": "Python 程序设计"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "description" in data
    assert len(data["description"]) > 0
    assert "usage_log_id" in data
    assert isinstance(data["usage_log_id"], int)
    assert "prompt_tokens" in data
    assert "completion_tokens" in data
