# services/chat_service.py
import uuid
import core.db as core_db

async def get_or_create_session(pdf_id: str, user_id: str | None, guest_name: str | None = None) -> dict:
    query = core_db.supabase_client.table("chat_sessions").select("*").eq("pdf_id", pdf_id)
    query = query.eq("user_id", user_id) if user_id else query.eq("guest_name", guest_name)
    existing = await query.execute()

    if existing.data:
        return existing.data[0]

    thread_id = str(uuid.uuid4())
    result = await core_db.supabase_client.table("chat_sessions").insert({
        "pdf_id": pdf_id,
        "user_id": user_id,
        "guest_name": guest_name,
        "langgraph_thread_id": thread_id,
    }).execute()
    return result.data[0]


async def save_message(session_id: str, role: str, content: str) -> dict:
    result = await core_db.supabase_client.table("chat_messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()
    return result.data[0]


async def get_messages_for_session(session_id: str) -> list[dict]:
    result = (
        await core_db.supabase_client.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data