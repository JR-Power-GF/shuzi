import json

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_to_response(task: Task, class_name: str) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        requirements=task.requirements,
        class_id=task.class_id,
        class_name=class_name,
        created_by=task.created_by,
        deadline=task.deadline,
        allowed_file_types=json.loads(task.allowed_file_types),
        max_file_size_mb=task.max_file_size_mb,
        allow_late_submission=task.allow_late_submission,
        late_penalty_percent=task.late_penalty_percent,
        status=task.status,
        grades_published=task.grades_published,
        created_at=task.created_at,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == data.class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    if current_user["role"] != "admin" and cls.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能为自己的班级创建任务")

    task = Task(
        title=data.title,
        description=data.description,
        requirements=data.requirements,
        class_id=data.class_id,
        created_by=current_user["id"],
        deadline=data.deadline,
        allowed_file_types=json.dumps(data.allowed_file_types),
        max_file_size_mb=data.max_file_size_mb,
        allow_late_submission=data.allow_late_submission,
        late_penalty_percent=data.late_penalty_percent,
    )
    db.add(task)
    await db.flush()

    return _task_to_response(task, cls.name)


@router.get("/my", response_model=list[TaskResponse])
async def get_my_tasks(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        class_id = user_result.scalar_one_or_none()
        if not class_id:
            return []
        result = await db.execute(
            select(Task)
            .where(Task.class_id == class_id)
            .where(Task.status == "active")
            .order_by(Task.deadline)
        )
    elif current_user["role"] == "teacher":
        result = await db.execute(
            select(Task)
            .where(Task.created_by == current_user["id"])
            .order_by(Task.created_at.desc())
        )
    else:
        return []

    tasks = result.scalars().all()
    response = []
    for task in tasks:
        cls_result = await db.execute(select(Class.name).where(Class.id == task.class_id))
        class_name = cls_result.scalar_one()
        response.append(_task_to_response(task, class_name))
    return response


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_detail(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if current_user["role"] == "admin":
        pass
    elif current_user["role"] == "teacher":
        if task.created_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该任务")
    elif current_user["role"] == "student":
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        if user_result.scalar_one() != task.class_id:
            raise HTTPException(status_code=403, detail="无权查看该任务")
    else:
        raise HTTPException(status_code=403)

    cls_result = await db.execute(select(Class.name).where(Class.id == task.class_id))
    class_name = cls_result.scalar_one()
    return _task_to_response(task, class_name)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    current_user=Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能编辑自己创建的任务")

    update_data = data.model_dump(exclude_unset=True)

    sub_count = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.task_id == task_id)
    )
    has_submissions = sub_count.scalar() > 0

    if has_submissions:
        if "allowed_file_types" in update_data:
            raise HTTPException(status_code=400, detail="已有提交，不能修改文件类型")
        if "deadline" in update_data and update_data["deadline"] is not None:
            earliest_result = await db.execute(
                select(func.min(Submission.submitted_at)).where(Submission.task_id == task_id)
            )
            earliest = earliest_result.scalar()
            if earliest and update_data["deadline"] < earliest:
                raise HTTPException(status_code=400, detail="截止日期不能早于最早提交时间")

    for field, value in update_data.items():
        if field == "allowed_file_types" and value is not None:
            setattr(task, field, json.dumps(value))
        else:
            setattr(task, field, value)
    await db.flush()

    cls_result = await db.execute(select(Class).where(Class.id == task.class_id))
    cls = cls_result.scalar_one()
    return _task_to_response(task, cls.name)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user=Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能删除自己创建的任务")

    sub_count = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.task_id == task_id)
    )
    if sub_count.scalar() > 0:
        raise HTTPException(status_code=400, detail="任务已有提交，无法删除")

    await db.delete(task)
    await db.flush()
    return {"message": "任务已删除"}


@router.post("/{task_id}/archive")
async def archive_task(
    task_id: int,
    current_user=Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current_user["role"] != "admin" and task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能归档自己创建的任务")

    task.status = "archived"
    await db.flush()
    return {"id": task.id, "status": "archived"}


@router.get("", response_model=dict)
async def list_tasks_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task)
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.offset(skip).limit(limit).order_by(Task.id.desc()))
    tasks = result.scalars().all()

    items = []
    for task in tasks:
        cls_result = await db.execute(select(Class).where(Class.id == task.class_id))
        cls = cls_result.scalar_one_or_none()
        class_name = cls.name if cls else ""
        items.append(_task_to_response(task, class_name))

    return {"items": items, "total": total}
