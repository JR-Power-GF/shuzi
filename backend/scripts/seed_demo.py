import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.class_ import Class
from app.models.user import User
from app.utils.security import hash_password


async def seed():
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Demo data already exists, skipping.")
            return

        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            real_name="系统管理员",
            role="admin",
            must_change_password=True,
        )
        db.add(admin)
        await db.flush()

        teacher = User(
            username="teacher1",
            password_hash=hash_password("teacher123"),
            real_name="王老师",
            role="teacher",
            must_change_password=True,
        )
        db.add(teacher)
        await db.flush()

        cls = Class(
            name="计算机网络1班",
            semester="2025-2026-2",
            teacher_id=teacher.id,
        )
        db.add(cls)
        await db.flush()

        student = User(
            username="student1",
            password_hash=hash_password("student123"),
            real_name="张三",
            role="student",
            primary_class_id=cls.id,
            must_change_password=True,
        )
        db.add(student)
        await db.flush()

        await db.commit()
        print(f"Created: admin({admin.id}), teacher1({teacher.id}), class({cls.id}), student1({student.id})")


if __name__ == "__main__":
    asyncio.run(seed())
