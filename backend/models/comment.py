from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

class CommentCreate(BaseModel):
    content: str
    guest_name: Optional[str] = None   # sirf tab chahiye jab user guest ho

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Comment content cannot be empty")
        return v

class CommentOut(BaseModel):
    id: UUID
    pdf_id: UUID
    user_id: Optional[UUID]
    guest_name: Optional[str]
    content: str
    created_at: datetime