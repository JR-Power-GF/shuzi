import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    class_id: int
    deadline: datetime
    allowed_file_types: List[str]
    max_file_size_mb: int = 50
    allow_late_submission: bool = False
    late_penalty_percent: Optional[float] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    class_id: int
    class_name: str
    created_by: int
    deadline: datetime
    allowed_file_types: List[str]
    max_file_size_mb: int
    allow_late_submission: bool
    late_penalty_percent: Optional[float] = None
    status: str
    grades_published: bool
    created_at: datetime
