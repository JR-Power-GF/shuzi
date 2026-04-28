from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    real_name: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    primary_class_id: Optional[int] = None


class UserSelfUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = Field(None, pattern=r'^(admin|teacher|student|facility_manager)$')
    primary_class_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: str
    role: str
    is_active: bool
    email: Optional[str] = None
    phone: Optional[str] = None
    primary_class_id: Optional[int] = None
    must_change_password: bool
    created_at: datetime


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
