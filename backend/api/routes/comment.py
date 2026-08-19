from fastapi import APIRouter, Depends, Header
from typing import Optional
from dependencies import get_current_user
from models.comment import CommentCreate, CommentOut
from services.comment_service import (
    add_comment_authenticated,
    add_comment_guest,
    get_comments_for_pdf,
)
from services.pdf_service import get_owned_pdf_or_403, get_pdf_by_share_token, make_pdf_id_to_str

comment_router = APIRouter(tags=["comments"])

# --- Authenticated owner route ---
@comment_router.post("/pdfs/{pdf_id}/comments", response_model=CommentOut)
async def create_comment(pdf_id: str, payload: CommentCreate, current_user: dict = Depends(get_current_user)):
    pdf_id = make_pdf_id_to_str(pdf_id)
    await get_owned_pdf_or_403(pdf_id, current_user["id"])   # ensure PDF exists + user owns it
    return await add_comment_authenticated(pdf_id, current_user["id"], payload)


@comment_router.get("/pdfs/{pdf_id}/comments", response_model=list[CommentOut])
async def list_comments(pdf_id: str, current_user: dict = Depends(get_current_user)):
    pdf_id = make_pdf_id_to_str(pdf_id)
    await get_owned_pdf_or_403(pdf_id, current_user["id"])
    return await get_comments_for_pdf(pdf_id)


# --- Public, guest (share-link) route ---
@comment_router.post("/shared/{share_token}/comments", response_model=CommentOut)
async def create_guest_comment(share_token: str, payload: CommentCreate):
    pdf = await get_pdf_by_share_token(share_token)
    return await add_comment_guest(pdf["id"], payload)


@comment_router.get("/shared/{share_token}/comments", response_model=list[CommentOut])
async def list_guest_comments(share_token: str):
    pdf = await get_pdf_by_share_token(share_token)
    return await get_comments_for_pdf(pdf["id"])