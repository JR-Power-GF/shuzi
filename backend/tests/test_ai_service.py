import pytest
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.services.ai import AIService, MockProvider, BudgetExceededError


@pytest.mark.asyncio(loop_scope="session")
async def test_get_config_reads_from_db(db_session: AsyncSession):
    db_session.add(AIConfig(key="model", value="gpt-4o"))
    db_session.add(AIConfig(key="budget_student", value="50000"))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)

    assert config["model"] == "gpt-4o"
    assert config["budget_student"] == 50000


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_within_limit(db_session: AsyncSession):
    user_id = 1
    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)
    remaining = await service.check_budget(db_session, user_id, "student", config)
    assert remaining == 50000


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_exceeded(db_session: AsyncSession):
    from app.models.ai_usage_log import AIUsageLog
    from app.models.user import User

    user_id = 1
    db_session.add(User(
        id=user_id, username="testbudget", password_hash="x",
        real_name="Test", role="student",
    ))
    await db_session.flush()

    db_session.add(AIUsageLog(
        user_id=user_id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=50000, completion_tokens=0, cost_microdollars=0,
        latency_ms=100, status="success",
    ))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)
    with pytest.raises(BudgetExceededError):
        await service.check_budget(db_session, user_id, "student", config)


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_first_call_of_day(db_session: AsyncSession):
    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)
    remaining = await service.check_budget(db_session, 999, "teacher", config)
    assert remaining == 200000
