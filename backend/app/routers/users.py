from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.user import User
from app.models.class_ import Class
from app.schemas.user import UserCreate, UserUpdate, UserSelfUpdate, UserResponse, UserListResponse
from app.utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_to_response(user):
    return UserResponse(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        role=user.role,
        is_active=user.is_active,
        email=user.email,
        phone=user.phone,
        primary_class_id=user.primary_class_id,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
    )


@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    if data.primary_class_id:
        cls = await db.execute(select(Class).where(Class.id == data.primary_class_id))
        if not cls.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="班级不存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        role=data.role,
        email=data.email,
        phone=data.phone,
        primary_class_id=data.primary_class_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    return _user_to_response(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if search:
        query = query.where(
            User.username.contains(search) | User.real_name.contains(search)
        )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.offset(skip).limit(limit).order_by(User.id))
    users = result.scalars().all()
    return UserListResponse(
        items=[_user_to_response(u) for u in users], total=total
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _user_to_response(user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserSelfUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.flush()
    return _user_to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.flush()
    return _user_to_response(user)


@router.put("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == current_user["id"]:
        raise HTTPException(status_code=400, detail="不能停用自己的账户")

    user.is_active = False
    await db.flush()
    return {"message": "用户已停用"}
