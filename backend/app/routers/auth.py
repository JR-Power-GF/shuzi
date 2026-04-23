import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    ResetPasswordRequest,
    UserBrief,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
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
        # Return error response directly instead of raising HTTPException.
        # get_db() commits on normal return, persisting the counter.
        # Raising triggers get_db()'s rollback and loses the counter.
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "用户名或密码错误"})

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


@router.post("/refresh")
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from app.utils.security import hash_token

    token_hash = hash_token(data.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    now = datetime.datetime.now(datetime.timezone.utc)
    if rt.expires_at.replace(tzinfo=datetime.timezone.utc) < now:
        raise HTTPException(status_code=401, detail="刷新令牌已过期")

    # Revoke old refresh token
    rt.revoked = True

    # Get user
    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    # Issue new token pair
    access_token = create_access_token(user.id, user.role, user.username)
    new_refresh_token_str = create_refresh_token(user.id)
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_token_str),
        expires_at=now + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token_str,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    data: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.utils.security import hash_token

    token_hash = hash_token(data.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if rt and rt.user_id == current_user["id"]:
        rt.revoked = True
        await db.flush()

    return {"message": "退出登录成功"}


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await db.flush()
    return {"message": "密码修改成功"}


@router.post("/reset-password/{user_id}")
async def reset_password(
    user_id: int,
    data: ResetPasswordRequest,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = True
    await db.flush()
    return {"message": "密码重置成功"}
