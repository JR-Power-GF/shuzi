import pytest
import json
from app.models.prompt_template import PromptTemplate
from app.services.prompts import PromptService


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
