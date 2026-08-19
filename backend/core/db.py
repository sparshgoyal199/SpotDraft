from supabase import acreate_client, AsyncClient
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client: AsyncClient | None = None   # abhi None, lifespan mein set hoga


async def init_supabase_client():
    global supabase_client
    supabase_client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase_client