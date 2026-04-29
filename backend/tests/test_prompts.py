import pytest
import json
from app.models.prompt_template import PromptTemplate
from app.services.prompts import PromptService
from tests.helpers import create_test_user, login_user, auth_headers


@pytest.mark.asyncio(loop_scope="session")
async def test_get_template(db_session):
    db_session.add(PromptTemplate(
        name="task_description",
        description="Generate task description",
        template_text="请为{course_name}课程生成关于{topic}的任务描述",
        variables=json.dumps(["course_name", "topic"]),
    ))
    await db_session.flush()

    service = PromptService()
    template = await service.get_template(db_session, "task_description")
    assert template["name"] == "task_description"
    assert "course_name" in template["variables"]


@pytest.mark.asyncio(loop_scope="session")
async def test_fill_template(db_session):
    db_session.add(PromptTemplate(
        name="test_tpl",
        description="test",
        template_text="你好 {name}，欢迎来到{course}",
        variables=json.dumps(["name", "course"]),
    ))
    await db_session.flush()

    service = PromptService()
    result = await service.fill_template(db_session, "test_tpl", {"name": "张三", "course": "Python"})
    assert result == "你好 张三，欢迎来到Python"


@pytest.mark.asyncio(loop_scope="session")
async def test_fill_template_missing_variable(db_session):
    db_session.add(PromptTemplate(
        name="test_missing",
        description="test",
        template_text="{a} and {b}",
        variables=json.dumps(["a", "b"]),
    ))
    await db_session.flush()

    service = PromptService()
    with pytest.raises(ValueError, match="Missing.*variable"):
        await service.fill_template(db_session, "test_missing", {"a": "x"})


@pytest.mark.asyncio(loop_scope="session")
async def test_fill_template_not_found(db_session):
    service = PromptService()
    with pytest.raises(ValueError, match="not found"):
        await service.fill_template(db_session, "nonexistent", {})


@pytest.mark.asyncio(loop_scope="session")
async def test_list_templates(client, db_session):
    await create_test_user(db_session, username="admin_p", role="admin")
    token = await login_user(client, "admin_p")

    db_session.add(PromptTemplate(
        name="task_description", description="test",
        template_text="生成任务描述", variables=json.dumps(["course_name"]),
    ))
    await db_session.flush()

    resp = await client.get("/api/prompts", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "task_description"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_template(client, db_session):
    await create_test_user(db_session, username="admin_p2", role="admin")
    token = await login_user(client, "admin_p2")

    db_session.add(PromptTemplate(
        name="test_tpl", description="test",
        template_text="旧内容 {name}", variables=json.dumps(["name"]),
    ))
    await db_session.flush()

    resp = await client.put(
        "/api/prompts/test_tpl",
        json={"template_text": "新内容 {name}"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["template_text"] == "新内容 {name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_template_invalid_variable(client, db_session):
    await create_test_user(db_session, username="admin_p3", role="admin")
    token = await login_user(client, "admin_p3")

    db_session.add(PromptTemplate(
        name="test_invalid", description="test",
        template_text="{a}", variables=json.dumps(["a"]),
    ))
    await db_session.flush()

    resp = await client.put(
        "/api/prompts/test_invalid",
        json={"template_text": "{a} and {b}"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_prompts_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu_p", role="student")
    token = await login_user(client, "stu_p")

    resp = await client.get("/api/prompts", headers=auth_headers(token))
    assert resp.status_code == 403
