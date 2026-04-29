from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PromptTemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    template_text: str
    variables: List[str]
    updated_at: datetime
    updated_by: Optional[int] = None


class PromptTemplateUpdate(BaseModel):
    template_text: str
