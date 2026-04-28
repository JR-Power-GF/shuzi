from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator


class VenueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    capacity: Optional[int] = Field(None, gt=0)
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class VenueUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    capacity: Optional[int] = None
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r'^(active|inactive|maintenance)$')
    external_id: Optional[str] = Field(None, max_length=100)


class VenueResponse(BaseModel):
    id: int
    name: str
    capacity: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    status: str
    external_id: Optional[str] = None
    availability: List[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class VenueListResponse(BaseModel):
    items: List[VenueResponse]
    total: int


class AvailabilitySlot(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}$')
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}$')

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AvailabilitySlotsUpdate(BaseModel):
    slots: List[AvailabilitySlot]


class BlackoutCreate(BaseModel):
    start_date: str
    end_date: str
    reason: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class BlackoutResponse(BaseModel):
    id: int
    venue_id: int
    start_date: str
    end_date: str
    reason: Optional[str] = None
