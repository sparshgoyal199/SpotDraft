# routers/chat.py
from fastapi import APIRouter, Depends
from dependencies import get_current_user
from services.pdf_service import get_owned_pdf_or_403, get_pdf_by_share_token
from services.chat_services import get_or_create_session, get_messages_for_session
from models.chat import ChatHistoryResponse, GuestIdentify
from services.pdf_service import make_pdf_id_to_str

chat_router = APIRouter(tags=["chat"])

@chat_router.get("/pdfs/{pdf_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(pdf_id: str, current_user: dict = Depends(get_current_user)):
    pdf_id = make_pdf_id_to_str(pdf_id)
    pdf = await get_owned_pdf_or_403(pdf_id, current_user["id"])
    session = await get_or_create_session(pdf_id, current_user["id"])
    messages = await get_messages_for_session(session["id"])

    return {"session_id": session["id"], "messages": messages}

@chat_router.post("/shared/{share_token}/chat/history", response_model=ChatHistoryResponse)
async def get_guest_chat_history(share_token: str, payload: GuestIdentify):
    pdf = await get_pdf_by_share_token(share_token)
    session = await get_or_create_session(pdf["id"], user_id=None, guest_name=payload.guest_name)
    messages = await get_messages_for_session(session["id"])
    return {"session_id": session["id"], "guest_name": payload.guest_name, "messages": messages}