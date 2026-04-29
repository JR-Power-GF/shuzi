import datetime as _dt
from typing import Optional, List

from pydantic import BaseModel, Field


class EquipmentCreate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    venue_id: Optional[int] = None
    description: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class EquipmentUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    venue_id: Optional[int] = None
    description: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class EquipmentStatusUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    status: str = Field(..., pattern=r'^(active|inactive|maintenance)$')


class EquipmentResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    serial_number: Optional[str] = None
    status: str
    venue_id: Optional[int] = None
    venue_name: Optional[str] = None
    description: Optional[str] = None
    external_id: Optional[str] = None
    created_at: _dt.datetime
    updated_at: _dt.datetime


class EquipmentListResponse(BaseModel):
    items: List[EquipmentResponse]
    total: int
