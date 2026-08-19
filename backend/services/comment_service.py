from fastapi import HTTPException
import core.db as core_db
from models.comment import CommentCreate

async def add_comment_authenticated(pdf_id: str, user_id: str, payload: CommentCreate) -> dict:
    # authenticated route pe guest_name ki zaroorat nahi, ignore karo agar bheja bhi ho
    result = await core_db.supabase_client.table("comments").insert({
        "pdf_id": pdf_id,
        "user_id": user_id,
        "guest_name": None,
        "content": payload.content,
    }).execute()
    return result.data[0]


async def add_comment_guest(pdf_id: str, payload: CommentCreate) -> dict:
    if not payload.guest_name or not payload.guest_name.strip():
        raise HTTPException(status_code=400, detail="guest_name is required for unauthenticated comments")

    result = await core_db.supabase_client.table("comments").insert({
        "pdf_id": pdf_id,
        "user_id": None,
        "guest_name": payload.guest_name,
        "content": payload.content,
    }).execute()
    return result.data[0]


async def get_comments_for_pdf(pdf_id: str) -> list[dict]:
    result = (
       await core_db.supabase_client.table("comments")
        .select("*")
        .eq("pdf_id", pdf_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data