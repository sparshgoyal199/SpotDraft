from fastapi import APIRouter, Depends
from fastapi import UploadFile,File
from typing import Annotated
from dependencies import get_current_user
from fastapi import HTTPException
from models.response_models import UploadResponse
import traceback
from pipeline.ingest_workflow import ingestion_workflow
from datetime import datetime, timezone

upload_router = APIRouter() 

@upload_router.post("/upload", response_model=UploadResponse)
async def upload_document(file: Annotated[UploadFile, File(description="A file read as UploadFile")], current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["id"]
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        initial_state = {"file": file, "user_id": user_id}
        final_state = await ingestion_workflow.ainvoke(initial_state)
        return {
            "id": final_state["pdf_id"],
            "filename": file.filename,
            "summary": final_state.get("summary"),
            "upload_date": datetime.now(timezone.utc),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error occurred while uploading document: {str(e)}")