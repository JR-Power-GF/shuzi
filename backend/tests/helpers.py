import json
import datetime

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.models.equipment import Equipment
from app.models.task import Task
from app.models.user import User
from app.models.venue import Venue


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


async def create_test_user(
    db: AsyncSession,
    *,
    username: str,
    password: str = "testpass123",
    role: str = "student",
    real_name: str = "测试用户",
    is_active: bool = True,
    primary_class_id: int = None,
) -> User:
    # Check if user already exists in this session (handles re-creation within same test)
    from sqlalchemy import select as sa_select
    existing = await db.execute(sa_select(User).where(User.username == username))
    existing_user = existing.scalar_one_or_none()
    if existing_user:
        return existing_user

    user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=real_name,
        role=role,
        is_active=is_active,
        primary_class_id=primary_class_id,
    )
    db.add(user)
    await db.flush()
    return user


async def create_test_class(
    db: AsyncSession,
    *,
    name: str = "测试班级",
    semester: str = "2025-2026-2",
    teacher_id: int = None,
) -> Class:
    cls = Class(name=name, semester=semester, teacher_id=teacher_id)
    db.add(cls)
    await db.flush()
    return cls


async def create_test_task(
    db: AsyncSession,
    *,
    title: str = "测试任务",
    class_id: int,
    created_by: int,
    deadline: datetime.datetime = None,
    allowed_file_types: list = None,
    **kwargs,
) -> Task:
    task = Task(
        title=title,
        class_id=class_id,
        created_by=created_by,
        deadline=deadline or datetime.datetime(2026, 12, 31),
        allowed_file_types=json.dumps(allowed_file_types or [".pdf", ".doc", ".docx"]),
        **kwargs,
    )
    db.add(task)
    await db.flush()
    return task


async def login_user(client, username: str, password: str = "testpass123") -> str:
    response = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_test_venue(
    db: AsyncSession,
    *,
    name: str = "Test Venue",
    capacity: int = None,
    location: str = None,
    status: str = "active",
    **kwargs,
) -> Venue:
    venue = Venue(name=name, capacity=capacity, location=location, status=status, **kwargs)
    db.add(venue)
    await db.flush()
    return venue


async def create_test_equipment(
    db: AsyncSession,
    *,
    name: str = "Test Equipment",
    category: str = None,
    serial_number: str = None,
    venue_id: int = None,
    status: str = "active",
    **kwargs,
) -> Equipment:
    equip = Equipment(
        name=name, category=category, serial_number=serial_number,
        venue_id=venue_id, status=status, **kwargs,
    )
    db.add(equip)
    await db.flush()
    return equip
