import datetime
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_config import AIConfig


@dataclass
class AIResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
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
            if row.key in ("budget_admin", "budget_teacher", "budget_student",
                           "price_input", "price_output"):
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
