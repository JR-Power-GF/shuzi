import glob
import os
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.task import Task
from app.models.user import User
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionFileBrief,
    GradeBrief,
)

router = APIRouter(prefix="/api", tags=["submissions"])


@router.post("/tasks/{task_id}/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    task_id: int,
    data: SubmissionCreate,
    current_user: dict = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    user_result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = user_result.scalar_one()

    if user.primary_class_id != task.class_id:
        raise HTTPException(status_code=403, detail="你不属于该任务的班级")

    now = datetime.datetime.utcnow()
    deadline = task.deadline.replace(tzinfo=None) if task.deadline.tzinfo else task.deadline
    is_late = now > deadline

    if is_late and not task.allow_late_submission:
        raise HTTPException(status_code=400, detail="已过截止日期，不允许迟交")

    file_infos = []
    for token in data.file_tokens:
        matches = glob.glob(os.path.join(settings.UPLOAD_DIR, f"{token}_*"))
        if not matches:
            raise HTTPException(status_code=400, detail=f"文件 {token} 不存在，请重新上传")
        file_infos.append((token, matches[0]))

    existing_result = await db.execute(
        select(Submission).where(
            Submission.task_id == task_id,
            Submission.student_id == current_user["id"],
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.version += 1
        existing.is_late = is_late
        existing.submitted_at = now
        existing.updated_at = now
        await db.flush()

        old_files_result = await db.execute(
            select(SubmissionFile).where(SubmissionFile.submission_id == existing.id)
        )
        for old_f in old_files_result.scalars().all():
            await db.delete(old_f)
        await db.flush()

        submission = existing
    else:
        submission = Submission(
            task_id=task_id,
            student_id=current_user["id"],
            is_late=is_late,
        )
        db.add(submission)
        await db.flush()

    for token, file_path in file_infos:
        original_name = os.path.basename(file_path).split("_", 1)[1]
        sf = SubmissionFile(
            submission_id=submission.id,
            file_name=original_name,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            file_type=os.path.splitext(original_name)[1],
        )
        db.add(sf)
    await db.flush()

    files_result = await db.execute(
        select(SubmissionFile).where(SubmissionFile.submission_id == submission.id)
    )
    files = [
        SubmissionFileBrief(id=f.id, file_name=f.file_name, file_size=f.file_size, file_type=f.file_type)
        for f in files_result.scalars().all()
    ]

    return SubmissionResponse(
        id=submission.id,
        task_id=submission.task_id,
        student_id=submission.student_id,
        version=submission.version,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        files=files,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")

    task_result = await db.execute(select(Task).where(Task.id == submission.task_id))
    task = task_result.scalar_one()

    if current_user["role"] == "admin":
        pass
    elif current_user["role"] == "teacher":
        if task.created_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该提交")
    elif current_user["role"] == "student":
        if submission.student_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该提交")
    else:
        raise HTTPException(status_code=403)

    user_result = await db.execute(select(User.real_name).where(User.id == submission.student_id))
    student_name = user_result.scalar_one_or_none()

    files_result = await db.execute(
        select(SubmissionFile).where(SubmissionFile.submission_id == submission.id)
    )
    files = [
        SubmissionFileBrief(id=f.id, file_name=f.file_name, file_size=f.file_size, file_type=f.file_type)
        for f in files_result.scalars().all()
    ]

    grade_data = None
    grade_result = await db.execute(select(Grade).where(Grade.submission_id == submission.id))
    grade = grade_result.scalar_one_or_none()

    if grade:
        show_grade = False
        if current_user["role"] in ("admin", "teacher"):
            show_grade = True
        elif current_user["role"] == "student" and task.grades_published:
            show_grade = True

        if show_grade:
            grade_data = GradeBrief(
                score=grade.score,
                penalty_applied=grade.penalty_applied,
                feedback=grade.feedback,
                graded_at=grade.graded_at,
            )

    return SubmissionResponse(
        id=submission.id,
        task_id=submission.task_id,
        student_id=submission.student_id,
        student_name=student_name,
        version=submission.version,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        files=files,
        grade=grade_data,
    )


@router.get("/tasks/{task_id}/submissions", response_model=list[SubmissionResponse])
async def list_task_submissions(
    task_id: int,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能查看自己任务的提交")

    result = await db.execute(
        select(Submission).where(Submission.task_id == task_id)
    )
    submissions = result.scalars().all()

    response = []
    for sub in submissions:
        user_result = await db.execute(select(User.real_name).where(User.id == sub.student_id))
        student_name = user_result.scalar_one_or_none()

        files_result = await db.execute(
            select(SubmissionFile).where(SubmissionFile.submission_id == sub.id)
        )
        files = [
            SubmissionFileBrief(id=f.id, file_name=f.file_name, file_size=f.file_size, file_type=f.file_type)
            for f in files_result.scalars().all()
        ]

        grade_result = await db.execute(select(Grade).where(Grade.submission_id == sub.id))
        grade = grade_result.scalar_one_or_none()
        grade_data = None
        if grade:
            grade_data = GradeBrief(
                score=grade.score,
                penalty_applied=grade.penalty_applied,
                feedback=grade.feedback,
                graded_at=grade.graded_at,
            )

        response.append(SubmissionResponse(
            id=sub.id,
            task_id=sub.task_id,
            student_id=sub.student_id,
            student_name=student_name,
            version=sub.version,
            is_late=sub.is_late,
            submitted_at=sub.submitted_at,
            updated_at=sub.updated_at,
            files=files,
            grade=grade_data,
        ))
    return response
