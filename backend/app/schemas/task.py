import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    class_id: int
    course_id: Optional[int] = None
    deadline: datetime
    allowed_file_types: List[str]
    max_file_size_mb: int = 50
    allow_late_submission: bool = False
    late_penalty_percent: Optional[float] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    course_id: Optional[int] = None
    deadline: Optional[datetime] = None
    allowed_file_types: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    allow_late_submission: Optional[bool] = None
    late_penalty_percent: Optional[float] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    class_id: int
    class_name: str
    course_id: Optional[int] = None
    created_by: int
    deadline: datetime
    allowed_file_types: List[str]
    max_file_size_mb: int
    allow_late_submission: bool
    late_penalty_percent: Optional[float] = None
    status: str
    grades_published: bool
    created_at: datetime


class TaskDescriptionGenerateRequest(BaseModel):
    title: str
    course_name: str = "实训课程"
    language: str = "中文"


class TaskDescriptionGenerateResponse(BaseModel):
    description: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int
