from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal, Optional

class MessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

class ChatHistoryResponse(BaseModel):
    session_id: UUID
    guest_name: Optional[str] = None
    messages: list[MessageOut]

class GuestIdentify(BaseModel):
    guest_name: str