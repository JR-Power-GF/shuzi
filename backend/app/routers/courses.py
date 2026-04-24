import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.schemas.course import CourseCreate, CourseDetailResponse, CourseProgressResponse, CourseResponse, CourseUpdate

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
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一学期已存在同名课程",
        )

    # Fetch teacher name
    result = await db.execute(select(User.real_name).where(User.id == current_user["id"]))
    teacher_name = result.scalar_one_or_none() or ""

    return _course_to_response(course, teacher_name)


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    data: CourseUpdate,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if current_user["role"] != "admin" and course.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能编辑自己的课程")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同一学期已存在同名课程",
        )

    # Fetch teacher name
    teacher_result = await db.execute(
        select(User.real_name).where(User.id == course.teacher_id)
    )
    teacher_name = teacher_result.scalar_one_or_none() or ""

    return _course_to_response(course, teacher_name)


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    semester: Optional[str] = Query(None),
    teacher_id_filter: Optional[int] = Query(None, alias="teacher_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        # Student sees courses via task-class join: tasks in their class that have a course_id
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        class_id = user_result.scalar_one_or_none()
        if not class_id:
            return []
        query = (
            select(Course)
            .join(Task, Task.course_id == Course.id)
            .where(Task.class_id == class_id)
            .where(Course.status == "active")
            .distinct()
            .order_by(Course.semester.desc(), Course.name)
        )
    elif current_user["role"] == "teacher":
        query = select(Course).where(Course.teacher_id == current_user["id"])
        if status_filter:
            query = query.where(Course.status == status_filter)
        query = query.order_by(Course.semester.desc(), Course.name)
    else:  # admin
        query = select(Course)
        if semester:
            query = query.where(Course.semester == semester)
        if teacher_id_filter:
            query = query.where(Course.teacher_id == teacher_id_filter)
        if status_filter:
            query = query.where(Course.status == status_filter)
        query = query.order_by(Course.semester.desc(), Course.name)

    result = await db.execute(query)
    courses = result.scalars().all()

    response = []
    for course in courses:
        teacher_name_result = await db.execute(
            select(User.real_name).where(User.id == course.teacher_id)
        )
        teacher_name = teacher_name_result.scalar_one()
        task_count_result = await db.execute(
            select(func.count()).select_from(Task).where(Task.course_id == course.id)
        )
        task_count = task_count_result.scalar()
        response.append(_course_to_response(course, teacher_name, task_count))
    return response


@router.get("/my", response_model=list[CourseProgressResponse])
async def student_course_cards(
    current_user: dict = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
):
    # 1. Get student's class_id
    user_result = await db.execute(
        select(User.primary_class_id).where(User.id == current_user["id"])
    )
    class_id = user_result.scalar_one_or_none()
    if not class_id:
        return []

    # 2. Find active courses via task-class join
    courses_result = await db.execute(
        select(Course)
        .join(Task, Task.course_id == Course.id)
        .where(Task.class_id == class_id)
        .where(Course.status == "active")
        .distinct()
        .order_by(Course.semester.desc(), Course.name)
    )
    courses = courses_result.scalars().all()

    # 3. For each course, compute progress
    response = []
    for course in courses:
        # Count active tasks in this course for this class
        task_count_result = await db.execute(
            select(func.count()).select_from(Task).where(
                Task.course_id == course.id,
                Task.class_id == class_id,
                Task.status == "active",
            )
        )
        task_count = task_count_result.scalar()

        # Count student's submissions for tasks in this course
        submitted_result = await db.execute(
            select(func.count()).select_from(Submission).where(
                Submission.task_id.in_(
                    select(Task.id).where(
                        Task.course_id == course.id,
                        Task.class_id == class_id,
                    )
                ),
                Submission.student_id == current_user["id"],
            )
        )
        submitted_count = submitted_result.scalar()

        # Count graded submissions (submissions with a Grade record)
        graded_result = await db.execute(
            select(func.count()).select_from(Submission).join(
                Grade, Grade.submission_id == Submission.id
            ).where(
                Submission.task_id.in_(
                    select(Task.id).where(
                        Task.course_id == course.id,
                        Task.class_id == class_id,
                    )
                ),
                Submission.student_id == current_user["id"],
            )
        )
        graded_count = graded_result.scalar()

        # Nearest future deadline
        deadline_result = await db.execute(
            select(func.min(Task.deadline)).where(
                Task.course_id == course.id,
                Task.class_id == class_id,
                Task.status == "active",
                Task.deadline > datetime.datetime.utcnow(),
            )
        )
        nearest_deadline = deadline_result.scalar_one_or_none()

        # Teacher name
        teacher_name_result = await db.execute(
            select(User.real_name).where(User.id == course.teacher_id)
        )
        teacher_name = teacher_name_result.scalar_one()

        response.append(CourseProgressResponse(
            id=course.id,
            name=course.name,
            description=course.description,
            semester=course.semester,
            teacher_name=teacher_name,
            task_count=task_count,
            submitted_count=submitted_count,
            graded_count=graded_count,
            nearest_deadline=nearest_deadline,
        ))
    return response


@router.get("/{course_id}", response_model=CourseDetailResponse)
async def get_course_detail(
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if current_user["role"] == "teacher" and course.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权查看该课程")
    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="学生请使用课程卡片接口")

    teacher_name_result = await db.execute(
        select(User.real_name).where(User.id == course.teacher_id)
    )
    teacher_name = teacher_name_result.scalar_one()

    task_result = await db.execute(
        select(Task).where(Task.course_id == course_id).order_by(Task.deadline)
    )
    tasks = task_result.scalars().all()
    task_list = []
    for t in tasks:
        cls_result = await db.execute(select(Class.name).where(Class.id == t.class_id))
        class_name = cls_result.scalar_one_or_none() or ""
        task_list.append({
            "id": t.id,
            "title": t.title,
            "class_name": class_name,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "status": t.status,
        })

    return CourseDetailResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        semester=course.semester,
        teacher_id=course.teacher_id,
        teacher_name=teacher_name,
        status=course.status,
        task_count=len(task_list),
        created_at=course.created_at,
        updated_at=course.updated_at,
        tasks=task_list,
    )


@router.post("/{course_id}/archive")
async def archive_course(
    course_id: int,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="课程不存在")

    if current_user["role"] != "admin" and course.teacher_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权归档此课程",
        )

    course.status = "archived"
    await db.flush()

    return {"id": course.id, "status": "archived"}


@router.delete("/{course_id}")
async def delete_course(
    course_id: int,
    current_user: dict = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="课程不支持删除，请使用归档",
    )
