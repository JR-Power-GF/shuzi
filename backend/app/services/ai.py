import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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
