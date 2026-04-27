import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import AdminDashboardResponse, DailyCount, TeacherDashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/admin", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    # Users by role
    role_result = await db.execute(
        select(User.role, func.count()).group_by(User.role)
    )
    users_by_role = {role: count for role, count in role_result.all()}
    total_users = sum(users_by_role.values())

    # Active courses
    active_courses = await db.execute(
        select(func.count()).select_from(Course).where(Course.status == "active")
    )
    total_active_courses = active_courses.scalar()

    # Active tasks
    active_tasks = await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "active")
    )
    total_active_tasks = active_tasks.scalar()

    # Submissions
    total_sub_result = await db.execute(
        select(func.count()).select_from(Submission)
    )
    total_submissions = total_sub_result.scalar()

    late_sub_result = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.is_late == True)  # noqa: E712
    )
    late_submissions = late_sub_result.scalar()

    # Pending grades: submissions with no Grade record
    pending_result = await db.execute(
        select(func.count()).select_from(Submission)
        .outerjoin(Grade, Grade.submission_id == Submission.id)
        .where(Grade.id.is_(None))
    )
    pending_grades = pending_result.scalar()

    # Average score
    avg_result = await db.execute(select(func.avg(Grade.score)))
    avg_score = avg_result.scalar()

    # Daily submissions last 7 days
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    daily_result = await db.execute(
        select(
            func.date(Submission.submitted_at).label("date"),
            func.count().label("count"),
        )
        .where(Submission.submitted_at >= seven_days_ago)
        .group_by(func.date(Submission.submitted_at))
        .order_by(func.date(Submission.submitted_at))
    )
    daily_submissions_last_7d = [
        DailyCount(date=str(row.date), count=row.count)
        for row in daily_result.all()
    ]

    return AdminDashboardResponse(
        total_users=total_users,
        users_by_role=users_by_role,
        total_active_courses=total_active_courses,
        total_active_tasks=total_active_tasks,
        total_submissions=total_submissions,
        late_submissions=late_submissions,
        pending_grades=pending_grades,
        avg_score=round(avg_score, 2) if avg_score is not None else None,
        daily_submissions_last_7d=daily_submissions_last_7d,
    )


@router.get("/teacher", response_model=TeacherDashboardResponse)
async def teacher_dashboard(
    current_user: dict = Depends(require_role(["teacher"])),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = current_user["id"]

    # Teacher's active courses
    my_courses = await db.execute(
        select(func.count()).select_from(Course).where(
            Course.teacher_id == teacher_id, Course.status == "active",
        )
    )
    my_active_courses = my_courses.scalar()

    # Teacher's active tasks
    my_tasks = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.created_by == teacher_id, Task.status == "active",
        )
    )
    my_active_tasks = my_tasks.scalar()

    # Submissions to teacher's tasks
    my_task_ids = select(Task.id).where(Task.created_by == teacher_id)

    total_sub = await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.task_id.in_(my_task_ids)
        )
    )
    my_total_submissions = total_sub.scalar()

    late_sub = await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.task_id.in_(my_task_ids), Submission.is_late == True,  # noqa: E712
        )
    )
    my_late_submissions = late_sub.scalar()

    # Pending grades for teacher's tasks
    pending = await db.execute(
        select(func.count()).select_from(Submission)
        .outerjoin(Grade, Grade.submission_id == Submission.id)
        .where(
            Submission.task_id.in_(my_task_ids), Grade.id.is_(None),
        )
    )
    my_pending_grades = pending.scalar()

    # Average score for teacher's tasks
    avg_result = await db.execute(
        select(func.avg(Grade.score))
        .join(Submission, Submission.id == Grade.submission_id)
        .where(Submission.task_id.in_(my_task_ids))
    )
    my_avg_score = avg_result.scalar()

    # Daily submissions last 7 days for teacher's tasks
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    daily_result = await db.execute(
        select(
            func.date(Submission.submitted_at).label("date"),
            func.count().label("count"),
        )
        .where(
            Submission.task_id.in_(my_task_ids),
            Submission.submitted_at >= seven_days_ago,
        )
        .group_by(func.date(Submission.submitted_at))
        .order_by(func.date(Submission.submitted_at))
    )
    my_daily_submissions_last_7d = [
        DailyCount(date=str(row.date), count=row.count)
        for row in daily_result.all()
    ]

    return TeacherDashboardResponse(
        my_active_courses=my_active_courses,
        my_active_tasks=my_active_tasks,
        my_total_submissions=my_total_submissions,
        my_late_submissions=my_late_submissions,
        my_pending_grades=my_pending_grades,
        my_avg_score=round(my_avg_score, 2) if my_avg_score is not None else None,
        my_daily_submissions_last_7d=my_daily_submissions_last_7d,
    )
