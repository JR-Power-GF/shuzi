import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserBrief
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    now = datetime.datetime.utcnow()
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=403, detail="账号已被锁定，请稍后重试")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOCKOUT_THRESHOLD:
            user.locked_until = now + datetime.timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES
            )
        await db.flush()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.failed_login_attempts = 0
    user.locked_until = None

    access_token = create_access_token(user.id, user.role, user.username)
    refresh_token_str = create_refresh_token(user.id)

    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token_str),
        expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await db.flush()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        must_change_password=user.must_change_password,
        user=UserBrief(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            role=user.role,
        ),
    )
