import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.services.model_manager import get_model_status


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("")
async def health(session: DatabaseSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/model")
async def model_health() -> JSONResponse:
    result = await get_model_status()
    status_code = 200 if result["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=result)
