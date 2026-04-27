import datetime
import time
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_config import AIConfig


@dataclass
class AIResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AIProvider(Protocol):
    async def generate(self, prompt: str, model: str) -> AIResponse:
        ...


class MockProvider:
    """Returns fixed responses for testing."""

    def __init__(self, response_text: str = "AI 生成的测试回复"):
        self.response_text = response_text

    async def generate(self, prompt: str, model: str) -> AIResponse:
        return AIResponse(
            text=self.response_text,
            prompt_tokens=len(prompt) // 4,
            completion_tokens=len(self.response_text) // 4,
        )


class AIServiceError(Exception):
    pass


class BudgetExceededError(Exception):
    pass


class AIService:
    def __init__(self, provider: AIProvider = None):
        if provider is None:
            provider = MockProvider()
        self.provider = provider

    async def _get_config(self, db: AsyncSession) -> dict:
        result = await db.execute(select(AIConfig))
        rows = result.scalars().all()
        config = {
            "model": settings.AI_MODEL,
            "budget_admin": 500000,
            "budget_teacher": 200000,
            "budget_student": 50000,
            "price_input": 0.15,
            "price_output": 0.60,
        }
        for row in rows:
            if row.key in ("budget_admin", "budget_teacher", "budget_student"):
                config[row.key] = int(row.value)
            elif row.key in ("price_input", "price_output"):
                config[row.key] = float(row.value)
            else:
                config[row.key] = row.value
        return config

    async def check_budget(self, db: AsyncSession, user_id: int, role: str, config: dict) -> int:
        from app.models.ai_usage_log import AIUsageLog

        budget_key = f"budget_{role}"
        budget = config.get(budget_key, 50000)

        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.coalesce(func.sum(
                AIUsageLog.prompt_tokens + AIUsageLog.completion_tokens
            ), 0)).where(
                AIUsageLog.user_id == user_id,
                AIUsageLog.created_at >= today_start,
            )
        )
        used = result.scalar()
        remaining = int(budget - used)
        if remaining <= 0:
            raise BudgetExceededError("今日 AI 调用额度已用完，请明天再试")
        return remaining

    async def _log_usage(
        self, db: AsyncSession, *, user_id: int, endpoint: str, model: str,
        prompt_tokens: int, completion_tokens: int, cost_microdollars: int,
        latency_ms: int, status: str,
    ) -> int:
        from app.models.ai_usage_log import AIUsageLog

        log = AIUsageLog(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_microdollars=cost_microdollars,
            latency_ms=latency_ms,
            status=status,
        )
        db.add(log)
        await db.flush()
        return log.id

    async def generate(
        self, *, db: AsyncSession, prompt: str, user_id: int,
        role: str, endpoint: str = "",
    ) -> dict:
        config = await self._get_config(db)
        await self.check_budget(db, user_id, role, config)

        model = config["model"]
        start = time.time()
        try:
            response = await self.provider.generate(prompt, model)
            latency_ms = int((time.time() - start) * 1000)
            cost = int(
                response.prompt_tokens * config.get("price_input", 0.15)
                + response.completion_tokens * config.get("price_output", 0.60)
            )
            log_id = await self._log_usage(
                db, user_id=user_id, endpoint=endpoint, model=model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cost_microdollars=cost, latency_ms=latency_ms, status="success",
            )
            return {
                "text": response.text,
                "usage_log_id": log_id,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "cost_microdollars": cost,
            }
        except BudgetExceededError:
            raise
        except AIServiceError:
            raise
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            try:
                await self._log_usage(
                    db, user_id=user_id, endpoint=endpoint, model=model,
                    prompt_tokens=0, completion_tokens=0, cost_microdollars=0,
                    latency_ms=latency_ms, status="error",
                )
            except Exception:
                pass
            raise AIServiceError("AI 服务暂时不可用") from e


class OpenAIProvider:
    """Real OpenAI API provider using AsyncOpenAI."""

    def __init__(self, api_key: str, base_url: str = ""):
        import httpx
        from openai import AsyncOpenAI

        kwargs = {"api_key": api_key, "timeout": httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)

    async def generate(self, prompt: str, model: str) -> AIResponse:
        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        choice = response.choices[0]
        usage = response.usage
        return AIResponse(
            text=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        if settings.AI_API_KEY:
            _ai_service = AIService(provider=OpenAIProvider(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL))
        else:
            _ai_service = AIService(provider=MockProvider())
    return _ai_service
