from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.user import UserSignup, UserLogin
import core.db as core_db
import uuid
from core.security import hash_password, verify_password, create_access_token

async def signup_user(payload: UserSignup) -> dict:
    existing = await core_db.supabase_client.table("users").select("id").eq("email", payload.email).execute()
    if len(existing.data) > 0:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(payload.password)

    result = await core_db.supabase_client.table("users").insert({
        "id": str(uuid.uuid4().hex),
        "name": payload.name,
        "email": payload.email,
        "password_hash": hashed,
    }).execute()
    return result.data[0] 

async def login_user(payload: UserLogin) -> str:
    result = await core_db.supabase_client.table("users").select("*").eq("email", payload.email).execute()
    if not result.data: raise HTTPException(status_code=401, detail="Invalid email or password")
    user = result.data[0]
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user['id'])})
    return token