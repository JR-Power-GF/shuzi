from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.user import User
from app.schemas.class_ import ClassCreate, ClassResponse, StudentBrief

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


@router.get("/my", response_model=list[ClassResponse])
async def get_my_classes(
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Class).where(Class.teacher_id == current_user["id"])
    )
    classes = result.scalars().all()

    response = []
    for cls in classes:
        teacher_name = None
        if cls.teacher_id:
            t_result = await db.execute(select(User.real_name).where(User.id == cls.teacher_id))
            teacher_name = t_result.scalar_one_or_none()

        count_result = await db.execute(
            select(func.count()).select_from(User).where(User.primary_class_id == cls.id)
        )
        student_count = count_result.scalar() or 0

        response.append(ClassResponse(
            id=cls.id,
            name=cls.name,
            semester=cls.semester,
            teacher_id=cls.teacher_id,
            teacher_name=teacher_name,
            student_count=student_count,
            created_at=cls.created_at,
        ))
    return response


@router.get("/{class_id}/students", response_model=list[StudentBrief])
async def get_class_students(
    class_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    if current_user["role"] not in ("admin",):
        if current_user["role"] == "teacher" and cls.teacher_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该班级学生")
        if current_user["role"] == "student":
            raise HTTPException(status_code=403, detail="无权查看班级学生列表")

    result = await db.execute(
        select(User.id, User.username, User.real_name)
        .where(User.primary_class_id == class_id)
        .order_by(User.id)
    )
    rows = result.all()
    return [StudentBrief(id=r[0], username=r[1], real_name=r[2]) for r in rows]
