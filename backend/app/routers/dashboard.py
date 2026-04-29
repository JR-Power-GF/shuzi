import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, _utcnow_naive
from app.dependencies.auth import require_role
from app.models.class_ import Class
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import (
    AdminDashboardResponse, CourseStatItem, CourseStatsResponse,
    DailyCount, TeacherDashboardResponse,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/admin", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    # Users by role (active only)
    role_result = await db.execute(
        select(User.role, func.count()).where(User.is_active == True).group_by(User.role)  # noqa: E712
    )
    users_by_role = {role: count for role, count in role_result.all()}
    total_users = sum(users_by_role.values())

    # Total classes
    classes_result = await db.execute(select(func.count()).select_from(Class))
    total_classes = classes_result.scalar()

    # Courses by status
    active_courses = await db.execute(
        select(func.count()).select_from(Course).where(Course.status == "active")
    )
    total_active_courses = active_courses.scalar()

    archived_courses = await db.execute(
        select(func.count()).select_from(Course).where(Course.status == "archived")
    )
    total_archived_courses = archived_courses.scalar()

    # Tasks by status
    active_tasks = await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "active")
    )
    total_active_tasks = active_tasks.scalar()

    archived_tasks = await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "archived")
    )
    total_archived_tasks = archived_tasks.scalar()

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

    # Graded: submissions with a Grade record
    graded_result = await db.execute(
        select(func.count()).select_from(Submission)
        .join(Grade, Grade.submission_id == Submission.id)
    )
    graded = graded_result.scalar()

    # Average score
    avg_result = await db.execute(select(func.avg(Grade.score)))
    avg_score = avg_result.scalar()

    # Nearby deadline: nearest future deadline among active tasks
    now = _utcnow_naive()
    deadline_result = await db.execute(
        select(Task.deadline).where(
            Task.status == "active", Task.deadline > now,
        ).order_by(Task.deadline).limit(1)
    )
    nearby_deadline_row = deadline_result.first()
    nearby_deadline = str(nearby_deadline_row[0]) if nearby_deadline_row else None

    # Daily submissions last 7 days
    seven_days_ago = now - datetime.timedelta(days=7)
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
        total_classes=total_classes,
        total_active_courses=total_active_courses,
        total_archived_courses=total_archived_courses,
        total_active_tasks=total_active_tasks,
        total_archived_tasks=total_archived_tasks,
        total_submissions=total_submissions,
        pending_grades=pending_grades,
        graded=graded,
        late_submissions=late_submissions,
        avg_score=round(avg_score, 1) if avg_score is not None else None,
        nearby_deadline=nearby_deadline,
        daily_submissions_last_7d=daily_submissions_last_7d,
    )


@router.get("/teacher", response_model=TeacherDashboardResponse)
async def teacher_dashboard(
    current_user: dict = Depends(require_role(["teacher"])),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = current_user["id"]

    # Teacher's classes
    my_classes_result = await db.execute(
        select(func.count()).select_from(Class).where(Class.teacher_id == teacher_id)
    )
    my_classes = my_classes_result.scalar()

    # Teacher's courses by status
    my_active_courses = await db.execute(
        select(func.count()).select_from(Course).where(
            Course.teacher_id == teacher_id, Course.status == "active",
        )
    )
    my_archived_courses = await db.execute(
        select(func.count()).select_from(Course).where(
            Course.teacher_id == teacher_id, Course.status == "archived",
        )
    )

    # Teacher's tasks by status
    my_active_tasks = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.created_by == teacher_id, Task.status == "active",
        )
    )
    my_archived_tasks = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.created_by == teacher_id, Task.status == "archived",
        )
    )

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

    # Graded for teacher's tasks
    graded = await db.execute(
        select(func.count()).select_from(Submission)
        .join(Grade, Grade.submission_id == Submission.id)
        .where(Submission.task_id.in_(my_task_ids))
    )
    my_graded = graded.scalar()

    # Average score for teacher's tasks
    avg_result = await db.execute(
        select(func.avg(Grade.score))
        .join(Submission, Submission.id == Grade.submission_id)
        .where(Submission.task_id.in_(my_task_ids))
    )
    my_avg_score = avg_result.scalar()

    # Nearby deadline: nearest future deadline among teacher's active tasks
    now = _utcnow_naive()
    deadline_result = await db.execute(
        select(Task.deadline).where(
            Task.created_by == teacher_id, Task.status == "active", Task.deadline > now,
        ).order_by(Task.deadline).limit(1)
    )
    nearby_deadline_row = deadline_result.first()
    my_nearby_deadline = str(nearby_deadline_row[0]) if nearby_deadline_row else None

    # Daily submissions last 7 days for teacher's tasks
    seven_days_ago = now - datetime.timedelta(days=7)
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
        my_classes=my_classes,
        my_active_courses=my_active_courses.scalar(),
        my_archived_courses=my_archived_courses.scalar(),
        my_active_tasks=my_active_tasks.scalar(),
        my_archived_tasks=my_archived_tasks.scalar(),
        my_total_submissions=my_total_submissions,
        my_pending_grades=my_pending_grades,
        my_graded=my_graded,
        my_late_submissions=my_late_submissions,
        my_avg_score=round(my_avg_score, 1) if my_avg_score is not None else None,
        my_nearby_deadline=my_nearby_deadline,
        my_daily_submissions_last_7d=my_daily_submissions_last_7d,
    )


@router.get("/courses", response_model=CourseStatsResponse)
async def course_stats(
    current_user: dict = Depends(require_role(["admin", "teacher"])),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user["id"]
    role = current_user["role"]

    # Base query: course info + teacher name
    query = (
        select(
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            User.real_name.label("teacher_name"),
        )
        .join(User, User.id == Course.teacher_id)
    )

    if role == "teacher":
        query = query.where(Course.teacher_id == user_id)

    course_rows = await db.execute(query)
    courses_data = course_rows.all()

    if not courses_data:
        return CourseStatsResponse(courses=[])

    course_ids = [row.course_id for row in courses_data]

    # Batch queries (5 queries total instead of 5N)
    task_counts_result = await db.execute(
        select(Task.course_id, func.count())
        .where(Task.course_id.in_(course_ids))
        .group_by(Task.course_id)
    )
    task_counts = dict(task_counts_result.all())

    sub_counts_result = await db.execute(
        select(Task.course_id, func.count())
        .select_from(Submission)
        .join(Task, Task.id == Submission.task_id)
        .where(Task.course_id.in_(course_ids))
        .group_by(Task.course_id)
    )
    sub_counts = dict(sub_counts_result.all())

    pending_result = await db.execute(
        select(Task.course_id, func.count())
        .select_from(Submission)
        .outerjoin(Grade, Grade.submission_id == Submission.id)
        .join(Task, Task.id == Submission.task_id)
        .where(Task.course_id.in_(course_ids), Grade.id.is_(None))
        .group_by(Task.course_id)
    )
    pending_counts = dict(pending_result.all())

    graded_result = await db.execute(
        select(Task.course_id, func.count())
        .select_from(Submission)
        .join(Grade, Grade.submission_id == Submission.id)
        .join(Task, Task.id == Submission.task_id)
        .where(Task.course_id.in_(course_ids))
        .group_by(Task.course_id)
    )
    graded_counts = dict(graded_result.all())

    avg_result = await db.execute(
        select(Task.course_id, func.avg(Grade.score))
        .select_from(Grade)
        .join(Submission, Submission.id == Grade.submission_id)
        .join(Task, Task.id == Submission.task_id)
        .where(Task.course_id.in_(course_ids))
        .group_by(Task.course_id)
    )
    avg_scores = dict(avg_result.all())

    result = []
    for row in courses_data:
        cid = row.course_id
        avg_val = avg_scores.get(cid)
        result.append(CourseStatItem(
            course_id=cid,
            course_name=row.course_name,
            teacher_name=row.teacher_name,
            task_count=task_counts.get(cid, 0),
            submission_count=sub_counts.get(cid, 0),
            pending_grade_count=pending_counts.get(cid, 0),
            graded_count=graded_counts.get(cid, 0),
            average_score=round(avg_val, 1) if avg_val is not None else None,
        ))

    result.sort(key=lambda c: c.submission_count, reverse=True)
    return CourseStatsResponse(courses=result)
