from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    file_tokens: List[str]


class SubmissionFileBrief(BaseModel):
    id: int
    file_name: str
    file_size: int
    file_type: str


class GradeBrief(BaseModel):
    score: float
    penalty_applied: Optional[float] = None
    feedback: Optional[str] = None
    graded_at: datetime


class SubmissionResponse(BaseModel):
    id: int
    task_id: int
    student_id: int
    student_name: Optional[str] = None
    version: int
    is_late: bool
    submitted_at: datetime
    updated_at: datetime
    files: List[SubmissionFileBrief] = []
    grade: Optional[GradeBrief] = None
