from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.ai_usage_log import AIUsageLog
from app.models.ai_feedback import AIFeedback
from app.models.ai_config import AIConfig
from app.models.user import User
from app.schemas.ai import (
    AIFeedbackIn, AIFeedbackOut, AIUsageOut, AIUsageWithBudget,
    AIStatsOut, AIStatsByUser, AIFeedbackSummary,
    AIConfigOut, AIConfigUpdate, AITestOut,
)
from app.services.ai import AIService, AIServiceError, BudgetExceededError, MockProvider
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_ai_service() -> AIService:
    if settings.AI_API_KEY:
        from app.services.ai import OpenAIProvider
        provider = OpenAIProvider(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)
        return AIService(provider=provider)
    return AIService(provider=MockProvider())


@router.post("/feedback", response_model=AIFeedbackOut)
async def submit_feedback(
    data: AIFeedbackIn,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    log_result = await db.execute(
        select(AIUsageLog).where(AIUsageLog.id == data.ai_usage_log_id)
    )
    log = log_result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="AI 调用记录不存在")
    if log.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能评价自己的 AI 调用")

    existing = await db.execute(
        select(AIFeedback).where(
            AIFeedback.ai_usage_log_id == data.ai_usage_log_id,
            AIFeedback.user_id == current_user["id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="已经评价过")

    feedback = AIFeedback(
        ai_usage_log_id=data.ai_usage_log_id,
        user_id=current_user["id"],
        rating=data.rating,
        comment=data.comment,
    )
    db.add(feedback)
    await db.flush()

    return AIFeedbackOut(
        id=feedback.id,
        ai_usage_log_id=feedback.ai_usage_log_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
