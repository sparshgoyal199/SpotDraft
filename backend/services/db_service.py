import os
import uuid
from fastapi import HTTPException
import core.db as core_db

async def uploading_file(pdf_id, user_id, filename, file_bytes, summary):

    original_filename = filename
    file_extension = os.path.splitext(original_filename)[1]

    unique_name = f"{uuid.uuid4().hex}{file_extension}"
    remote_path = f"uploads/{unique_name}"

    bucket_name = os.getenv("BUCKET_NAME")

    try:
        # Upload the PDF to Storage
        await core_db.supabase_client.storage.from_(bucket_name).upload(
            path=remote_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"},
        )

        # Insert the metadata into the database
        db_response = (
            await core_db.supabase_client.table("pdfs")
            .insert(
                {
                     "id": pdf_id,
                     "user_id": user_id,
                    "filename": original_filename,
                    "storage_path": remote_path,
                    "summary": summary,
                }
            )
            .execute()
        )

        return None
    except HTTPException:
            raise
    
    except Exception as e:
        # Roll back the uploaded file
        try:
           await core_db.supabase_client.storage.from_(bucket_name).remove(
                [remote_path]
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {e}",
        )