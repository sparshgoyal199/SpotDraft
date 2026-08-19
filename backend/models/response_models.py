from pydantic import BaseModel
from datetime import datetime

class QueryResponse(BaseModel):
    answer: str

class DeleteSessionResponse(BaseModel):
    message: str

class UploadResponse(BaseModel):
    id: str
    filename: str
    summary: str | None = None
    upload_date: datetime
