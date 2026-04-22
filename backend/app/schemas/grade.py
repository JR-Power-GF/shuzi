from typing import Optional

from pydantic import BaseModel


class GradeCreate(BaseModel):
    submission_id: int
    score: float
    feedback: Optional[str] = None


class GradeResponse(BaseModel):
    id: int
    submission_id: int
    score: float
    penalty_applied: Optional[float] = None
    feedback: Optional[str] = None
    graded_by: int
