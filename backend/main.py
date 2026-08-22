from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes.query import query_router
from api.routes.auth import auth_router
from api.routes.upload import upload_router
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from api.routes.comment import comment_router
from core.checkpointer import run_checkpointer_migrations, pool, init_checkpointer
from api.routes.pdf import pdf_router
from api.routes.chat import chat_router
from core.db import init_supabase_client

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pehle migrations, phir async pool open
    run_checkpointer_migrations()
    await init_supabase_client()
    await init_checkpointer()  

    yield  # Yahan app chalega

    # Shutdown: pool band karo
    import core.db as core_db
    await pool.close()
    await core_db.supabase_client.postgrest.session.aclose()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(upload_router)
app.include_router(auth_router)
app.include_router(pdf_router)
app.include_router(comment_router)
app.include_router(chat_router)


@app.get("/")
async def serve_login():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/viewer/{pdf_id}")
async def serve_viewer(pdf_id: str):
    return FileResponse(FRONTEND_DIR / "viewer.html")


@app.get("/shared/{share_token}")
async def serve_shared(share_token: str):
    return FileResponse(FRONTEND_DIR / "shared.html")


app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)