from typing import Optional, List

from pydantic import BaseModel, Field


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


class BulkGradeItem(BaseModel):
    submission_id: int
    score: float = Field(ge=0, le=100)
    feedback: Optional[str] = None


class BulkGradeRequest(BaseModel):
    grades: List[BulkGradeItem]
