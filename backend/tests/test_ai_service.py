import pytest
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.models.ai_usage_log import AIUsageLog
from app.services.ai import AIService, AIServiceError, BudgetExceededError, MockProvider, AIResponse


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


@pytest.mark.asyncio(loop_scope="session")
async def test_log_usage_success(db_session: AsyncSession):
    from sqlalchemy import select
    from app.models.ai_usage_log import AIUsageLog
    from app.models.user import User

    user_id = 1
    db_session.add(User(
        id=user_id, username="testlogsuccess", password_hash="x",
        real_name="Test", role="student",
    ))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    log_id = await service._log_usage(
        db_session, user_id=user_id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, cost_microdollars=45,
        latency_ms=200, status="success",
    )
    assert log_id is not None

    result = await db_session.execute(select(AIUsageLog).where(AIUsageLog.id == log_id))
    log = result.scalar_one()
    assert log.status == "success"
    assert log.cost_microdollars == 45
    assert log.prompt_tokens == 100


@pytest.mark.asyncio(loop_scope="session")
async def test_log_usage_error(db_session: AsyncSession):
    from sqlalchemy import select
    from app.models.ai_usage_log import AIUsageLog
    from app.models.user import User

    user_id = 1
    db_session.add(User(
        id=user_id, username="testlogerror", password_hash="x",
        real_name="Test", role="student",
    ))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    log_id = await service._log_usage(
        db_session, user_id=user_id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=0, completion_tokens=0, cost_microdollars=0,
        latency_ms=500, status="error",
    )
    result = await db_session.execute(select(AIUsageLog).where(AIUsageLog.id == log_id))
    log = result.scalar_one()
    assert log.status == "error"
    assert log.prompt_tokens == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_success(db_session: AsyncSession):
    from tests.helpers import create_test_user
    user = await create_test_user(db_session, username="gen_teacher", role="teacher")
    service = AIService(provider=MockProvider(response_text="这是生成的文本"))
    result = await service.generate(
        db=db_session,
        prompt="生成一个任务描述",
        user_id=user.id,
        role="teacher",
        endpoint="test_endpoint",
    )
    assert result["text"] == "这是生成的文本"
    assert result["usage_log_id"] is not None
    assert result["prompt_tokens"] > 0

    result2 = await db_session.execute(
        select(AIUsageLog).where(AIUsageLog.id == result["usage_log_id"])
    )
    log = result2.scalar_one()
    assert log.endpoint == "test_endpoint"
    assert log.status == "success"


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_provider_error(db_session: AsyncSession):
    from tests.helpers import create_test_user
    user = await create_test_user(db_session, username="err_teacher", role="teacher")

    class FailingProvider:
        async def generate(self, prompt: str, model: str) -> AIResponse:
            raise RuntimeError("provider timeout")

    service = AIService(provider=FailingProvider())
    with pytest.raises(AIServiceError):
        await service.generate(
            db=db_session, prompt="test", user_id=user.id, role="teacher", endpoint="test",
        )

    result = await db_session.execute(
        select(AIUsageLog).where(AIUsageLog.status == "error")
    )
    error_log = result.scalar_one_or_none()
    assert error_log is not None
    assert error_log.prompt_tokens == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_budget_exceeded(db_session: AsyncSession):
    from tests.helpers import create_test_user
    user = await create_test_user(db_session, username="budget_stu", role="student")

    db_session.add(AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=50000, completion_tokens=0, cost_microdollars=0,
        latency_ms=100, status="success",
    ))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    with pytest.raises(BudgetExceededError):
        await service.generate(
            db=db_session, prompt="test", user_id=user.id, role="student", endpoint="test",
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_cost_calculation(db_session: AsyncSession):
    from tests.helpers import create_test_user
    user = await create_test_user(db_session, username="cost_admin", role="admin")

    class FixedTokenProvider:
        async def generate(self, prompt: str, model: str) -> AIResponse:
            return AIResponse(text="response", prompt_tokens=500, completion_tokens=200)

    db_session.add(AIConfig(key="price_input", value="0.15"))
    db_session.add(AIConfig(key="price_output", value="0.60"))
    await db_session.flush()

    service = AIService(provider=FixedTokenProvider())
    result = await service.generate(
        db=db_session, prompt="test", user_id=user.id, role="admin", endpoint="cost_test",
    )

    log_result = await db_session.execute(
        select(AIUsageLog).where(AIUsageLog.id == result["usage_log_id"])
    )
    log = log_result.scalar_one()
    assert log.cost_microdollars == int(500 * 0.15 + 200 * 0.60)


@pytest.mark.asyncio(loop_scope="session")
async def test_openai_provider_creates_client():
    from app.services.ai import OpenAIProvider
    provider = OpenAIProvider(api_key="test-key", base_url="https://api.example.com/v1")
    assert provider.api_key == "test-key"
    assert provider.base_url == "https://api.example.com/v1"


def test_get_ai_service_returns_mock_by_default():
    from app.services.ai import get_ai_service
    service = get_ai_service()
    assert isinstance(service.provider, MockProvider)
