from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.course import Course
from app.models.user import User
from app.schemas.course import CourseCreate, CourseResponse

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _course_to_response(course: Course, teacher_name: str, task_count: int = 0) -> CourseResponse:
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        semester=course.semester,
        teacher_id=course.teacher_id,
        teacher_name=teacher_name,
        status=course.status,
        task_count=task_count,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate course name in same semester by same teacher
    existing = await db.execute(
        select(Course).where(
            Course.name == data.name,
            Course.semester == data.semester,
            Course.teacher_id == current_user["id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一学期已存在同名课程",
        )

    course = Course(
        name=data.name,
        description=data.description,
        semester=data.semester,
        teacher_id=current_user["id"],
    )
    db.add(course)
    await db.flush()

    # Fetch teacher name
    result = await db.execute(select(User.real_name).where(User.id == current_user["id"]))
    teacher_name = result.scalar_one_or_none() or ""

    return _course_to_response(course, teacher_name)
