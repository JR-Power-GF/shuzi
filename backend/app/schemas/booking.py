from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator


class EquipmentItem(BaseModel):
    id: int
    name: str


class BookingCreate(BaseModel):
    model_config = {"extra": "forbid"}

    venue_id: int
    title: str = Field(..., min_length=1, max_length=200)
    purpose: Optional[str] = None
    start_time: datetime
    end_time: datetime
    equipment_ids: List[int] = Field(default_factory=list)
    course_id: Optional[int] = None
    class_id: Optional[int] = None
    task_id: Optional[int] = None
    client_ref: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class BookingUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    purpose: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    equipment_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def validate_time_range(self):
        # Only validates when both fields are present. Partial updates
        # (only start_time or only end_time) pass through intentionally —
        # the route handler must load the existing booking and re-validate
        # the combined time range before persisting.
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class BookingResponse(BaseModel):
    id: int
    venue_id: int
    venue_name: Optional[str] = None
    title: str
    purpose: Optional[str] = None
    start_time: datetime
    end_time: datetime
    booked_by: int
    status: str
    derived_status: Optional[str] = None
    course_id: Optional[int] = None
    class_id: Optional[int] = None
    task_id: Optional[int] = None
    client_ref: Optional[str] = None
    equipment: List[EquipmentItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BookingListResponse(BaseModel):
    items: List[BookingResponse]
    total: int
