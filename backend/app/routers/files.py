import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.task import Task
from app.models.user import User
from app.schemas.file import FileUploadResponse

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    filename = file.filename or "unnamed"
    file_ext = os.path.splitext(filename)[1].lower()

    if file_ext not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的文件类型: {file_ext}",
        )

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail=f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)",
        )

    file_token = str(uuid.uuid4())
    final_name = f"{file_token}_{filename}"
    final_path = os.path.join(settings.UPLOAD_DIR, final_name)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(final_path, "wb") as f:
        f.write(contents)

    return FileUploadResponse(
        file_token=file_token,
        file_name=filename,
        file_size=len(contents),
        file_type=file_ext,
    )


@router.get("/{file_id}")
async def download_file(
    file_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SubmissionFile).where(SubmissionFile.id == file_id))
    sf = result.scalar_one_or_none()
    if not sf:
        raise HTTPException(status_code=404, detail="文件不存在")

    sub_result = await db.execute(select(Submission).where(Submission.id == sf.submission_id))
    submission = sub_result.scalar_one()

    task_result = await db.execute(select(Task).where(Task.id == submission.task_id))
    task = task_result.scalar_one()

    if current_user["role"] == "admin":
        pass
    elif current_user["role"] == "teacher":
        if task.created_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权下载该文件")
    elif current_user["role"] == "student":
        if submission.student_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权下载该文件")
    else:
        raise HTTPException(status_code=403)

    if not os.path.exists(sf.file_path):
        raise HTTPException(status_code=404, detail="文件已被删除")

    return FileResponse(
        path=sf.file_path,
        filename=sf.file_name,
        media_type="application/octet-stream",
    )
