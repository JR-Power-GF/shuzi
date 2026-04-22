from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.user import User
from app.schemas.class_ import ClassCreate, ClassResponse

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    data: ClassCreate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cls = Class(name=data.name, semester=data.semester, teacher_id=data.teacher_id)
    db.add(cls)
    await db.flush()

    teacher_name = None
    if cls.teacher_id:
        result = await db.execute(select(User.real_name).where(User.id == cls.teacher_id))
        teacher_name = result.scalar_one_or_none()

    count_result = await db.execute(
        select(func.count()).select_from(User).where(User.primary_class_id == cls.id)
    )
    student_count = count_result.scalar() or 0

    return ClassResponse(
        id=cls.id,
        name=cls.name,
        semester=cls.semester,
        teacher_id=cls.teacher_id,
        teacher_name=teacher_name,
        student_count=student_count,
        created_at=cls.created_at,
    )
