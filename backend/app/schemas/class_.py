from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClassCreate(BaseModel):
    name: str
    semester: str
    teacher_id: Optional[int] = None


class ClassResponse(BaseModel):
    id: int
    name: str
    semester: str
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    student_count: int = 0
    created_at: datetime


class StudentBrief(BaseModel):
    id: int
    username: str
    real_name: str
