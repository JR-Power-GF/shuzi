import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.schemas.grade import GradeCreate, GradeResponse, BulkGradeRequest

router = APIRouter(prefix="/api", tags=["grades"])


@router.post("/tasks/{task_id}/grades", response_model=GradeResponse)
async def grade_submission(
    task_id: int,
    data: GradeCreate,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能评自己创建的任务")

    if data.score < 0 or data.score > 100:
        raise HTTPException(status_code=422, detail="分数必须在 0-100 之间")

    sub_result = await db.execute(select(Submission).where(Submission.id == data.submission_id))
    submission = sub_result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")

    if submission.task_id != task_id:
        raise HTTPException(status_code=400, detail="提交不属于该任务")

    penalty_applied = None
    if submission.is_late and task.late_penalty_percent:
        penalty_applied = round(data.score * task.late_penalty_percent / 100, 2)

    existing = await db.execute(
        select(Grade).where(Grade.submission_id == data.submission_id)
    )
    existing_grade = existing.scalar_one_or_none()

    if existing_grade:
        existing_grade.score = data.score
        existing_grade.feedback = data.feedback
        existing_grade.penalty_applied = penalty_applied
        existing_grade.graded_by = current_user["id"]
        await db.flush()
        grade = existing_grade
    else:
        grade = Grade(
            submission_id=data.submission_id,
            score=data.score,
            feedback=data.feedback,
            penalty_applied=penalty_applied,
            graded_by=current_user["id"],
        )
        db.add(grade)
        await db.flush()

    return GradeResponse(
        id=grade.id,
        submission_id=grade.submission_id,
        score=grade.score,
        penalty_applied=grade.penalty_applied,
        feedback=grade.feedback,
        graded_by=grade.graded_by,
    )


@router.post("/tasks/{task_id}/grades/publish")
async def publish_grades(
    task_id: int,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能发布自己任务的成绩")

    task.grades_published = True
    task.grades_published_at = datetime.datetime.utcnow()
    task.grades_published_by = current_user["id"]
    await db.flush()

    return {"grades_published": True, "task_id": task_id}


@router.post("/tasks/{task_id}/grades/unpublish")
async def unpublish_grades(
    task_id: int,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能取消发布自己任务的成绩")

    task.grades_published = False
    task.grades_published_at = None
    task.grades_published_by = None
    await db.flush()

    return {"grades_published": False, "task_id": task_id}


@router.post("/tasks/{task_id}/grades/bulk")
async def bulk_grade(
    task_id: int,
    data: BulkGradeRequest,
    current_user=Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能评自己创建的任务")

    graded_count = 0
    for item in data.grades:
        sub_result = await db.execute(
            select(Submission).where(Submission.id == item.submission_id)
        )
        submission = sub_result.scalar_one_or_none()
        if not submission or submission.task_id != task_id:
            continue

        penalty_applied = None
        if submission.is_late and task.late_penalty_percent:
            penalty_applied = round(item.score * task.late_penalty_percent / 100, 2)

        existing = await db.execute(
            select(Grade).where(Grade.submission_id == submission.id)
        )
        grade = existing.scalar_one_or_none()
        if grade:
            grade.score = item.score
            grade.feedback = item.feedback
            grade.penalty_applied = penalty_applied
            grade.graded_by = current_user["id"]
        else:
            grade = Grade(
                submission_id=submission.id,
                score=item.score,
                feedback=item.feedback,
                penalty_applied=penalty_applied,
                graded_by=current_user["id"],
            )
            db.add(grade)
        graded_count += 1

    await db.flush()
    return {"graded_count": graded_count}
