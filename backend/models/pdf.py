from pydantic import BaseModel
from uuid import UUID

class ShareResponse(BaseModel):
    share_token: UUID
    share_url: str

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal

class PdfListItem(BaseModel):
    id: UUID
    filename: str
    upload_date: datetime
    summary: Optional[str] = None


class PdfDetail(BaseModel):
    id: UUID
    filename: str
    upload_date: datetime
    summary: Optional[str] = None
    file_url: Optional[str] = None      
    share_token: Optional[UUID] = None   


class SharedPdfDetail(BaseModel):
    id: UUID
    filename: str
    upload_date: datetime
    summary: Optional[str] = None
    file_url: Optional[str] = None