"""XR session and event response schemas (Pydantic v2)."""
import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class XRSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    booking_id: int
    provider: str
    external_session_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    retry_count: int = 0
    last_retry_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class XRSessionListResponse(BaseModel):
    items: List[XRSessionResponse]
    total: int


class XREventResponse(BaseModel):
    id: int
    event_id: str
    provider: str
    event_type: str
    processed: bool
    processing_error: Optional[str] = None
    signature_verified: bool
    created_at: datetime.datetime


class XRSessionRetryResponse(BaseModel):
    session_id: int
    status: str
    message: str


class XRCallbackResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
