from datetime import datetime as dt
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


@router.get("/usage", response_model=AIUsageWithBudget)
async def query_usage(
    user_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AIUsageLog)
    if user_id:
        query = query.where(AIUsageLog.user_id == user_id)
    if start_date:
        query = query.where(AIUsageLog.created_at >= dt.fromisoformat(start_date))
    if end_date:
        query = query.where(AIUsageLog.created_at <= dt.fromisoformat(end_date))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.order_by(AIUsageLog.id.desc()).limit(100))
    logs = result.scalars().all()

    items = [
        AIUsageOut(
            id=l.id, user_id=l.user_id, endpoint=l.endpoint, model=l.model,
            prompt_tokens=l.prompt_tokens, completion_tokens=l.completion_tokens,
            cost_microdollars=l.cost_microdollars, latency_ms=l.latency_ms,
            status=l.status, created_at=l.created_at,
        ) for l in logs
    ]

    target_user_id = user_id or current_user["id"]
    user_result = await db.execute(select(User.role).where(User.id == target_user_id))
    role = user_result.scalar_one_or_none() or "student"

    config_result = await db.execute(select(AIConfig))
    configs = {c.key: c.value for c in config_result.scalars().all()}
    budget_limit = int(configs.get(f"budget_{role}", "50000"))

    today_start = dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    used_result = await db.execute(
        select(func.coalesce(func.sum(
            AIUsageLog.prompt_tokens + AIUsageLog.completion_tokens
        ), 0)).where(
            AIUsageLog.user_id == target_user_id,
            AIUsageLog.created_at >= today_start,
        )
    )
    budget_used = int(used_result.scalar())

    return AIUsageWithBudget(
        items=items, total=total,
        budget_limit=budget_limit, budget_used=budget_used,
        budget_remaining=max(0, budget_limit - budget_used),
    )


@router.get("/stats/feedback", response_model=AIFeedbackSummary)
async def get_feedback_summary(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    pos_result = await db.execute(
        select(func.count()).select_from(AIFeedback).where(AIFeedback.rating > 0)
    )
    neg_result = await db.execute(
        select(func.count()).select_from(AIFeedback).where(AIFeedback.rating < 0)
    )
    recent_neg = await db.execute(
        select(AIFeedback).where(AIFeedback.rating < 0).order_by(AIFeedback.created_at.desc()).limit(10)
    )
    recent = [
        {"id": f.id, "comment": f.comment, "created_at": f.created_at.isoformat()}
        for f in recent_neg.scalars().all()
    ]
    return AIFeedbackSummary(
        positive_count=pos_result.scalar(),
        negative_count=neg_result.scalar(),
        recent_negative=recent,
    )


@router.get("/stats", response_model=AIStatsOut)
async def get_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AIUsageLog)
    if start_date:
        query = query.where(AIUsageLog.created_at >= dt.fromisoformat(start_date))
    if end_date:
        query = query.where(AIUsageLog.created_at <= dt.fromisoformat(end_date))

    sub = query.subquery()
    agg = await db.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(sub.c.prompt_tokens), 0).label("pt"),
            func.coalesce(func.sum(sub.c.completion_tokens), 0).label("ct"),
            func.coalesce(func.sum(sub.c.cost_microdollars), 0).label("cost"),
            func.coalesce(func.avg(sub.c.latency_ms), 0).label("avg_lat"),
        ).select_from(sub)
    )
    row = agg.one()

    success_sub = query.where(AIUsageLog.status == "success").subquery()
    success_count = await db.execute(
        select(func.count()).select_from(success_sub)
    )
    total = row.total or 0
    success_rate = (success_count.scalar() / total) if total > 0 else 0.0

    return AIStatsOut(
        total_calls=total,
        total_prompt_tokens=int(row.pt),
        total_completion_tokens=int(row.ct),
        total_cost_microdollars=int(row.cost),
        success_rate=round(success_rate, 2),
        avg_latency_ms=round(float(row.avg_lat), 1),
    )
