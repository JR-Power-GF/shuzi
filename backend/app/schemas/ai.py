from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class AIFeedbackIn(BaseModel):
    ai_usage_log_id: int
    rating: int = Field(..., ge=-1, le=1)
    comment: Optional[str] = None


class AIFeedbackOut(BaseModel):
    id: int
    ai_usage_log_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class AIUsageOut(BaseModel):
    id: int
    user_id: int
    endpoint: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_microdollars: int
    latency_ms: int
    status: str
    created_at: datetime


class AIUsageWithBudget(BaseModel):
    items: List[AIUsageOut]
    total: int
    budget_limit: int
    budget_used: int
    budget_remaining: int


class AIStatsOut(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_microdollars: int
    success_rate: float
    avg_latency_ms: float


class AIFeedbackSummary(BaseModel):
    positive_count: int
    negative_count: int
    recent_negative: List[dict]


class AIConfigOut(BaseModel):
    model: str
    budget_admin: int
    budget_teacher: int
    budget_student: int
    is_configured: bool


class AIConfigUpdate(BaseModel):
    model: Optional[str] = None
    budget_admin: Optional[int] = Field(None, ge=0)
    budget_teacher: Optional[int] = Field(None, ge=0)
    budget_student: Optional[int] = Field(None, ge=0)


class AITestOut(BaseModel):
    text: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int
