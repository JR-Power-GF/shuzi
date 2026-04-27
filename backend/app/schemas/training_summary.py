from datetime import datetime

from pydantic import BaseModel, Field


class SummaryGenerateResponse(BaseModel):
    content: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int


class SummarySaveRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    status: str = Field("draft", pattern=r"^(draft|submitted)$")


class SummaryResponse(BaseModel):
    id: int
    course_id: int
    content: str
    status: str
    created_at: datetime
    updated_at: datetime
