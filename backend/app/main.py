from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NAME
from app.schemas import ChatRequest, ChatResponse
from app.services.chat import generate_reply


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(title=APP_NAME)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = await generate_reply(request.messages)
    return ChatResponse(reply=reply)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
