import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse

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
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == data.class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    if cls.teacher_id != current_user["id"]:
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
