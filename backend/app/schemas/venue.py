from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class VenueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    capacity: Optional[int] = None
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
    created_at: datetime
    updated_at: datetime


class VenueListResponse(BaseModel):
    items: List[VenueResponse]
    total: int
