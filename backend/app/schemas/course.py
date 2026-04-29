from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    semester: str = Field(..., pattern=r'^\d{4}-\d{4}-[12]$')


class CourseUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    semester: str
    teacher_id: int
    teacher_name: Optional[str] = None
    status: str
    task_count: int = 0
    created_at: datetime
    updated_at: datetime


class CourseTaskItem(BaseModel):
    id: int
    title: str
    class_name: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


class CourseDetailResponse(CourseResponse):
    tasks: List[CourseTaskItem] = []


class CourseProgressResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    semester: str
    teacher_name: Optional[str] = None
    task_count: int = 0
    submitted_count: int = 0
    graded_count: int = 0
    nearest_deadline: Optional[datetime] = None
