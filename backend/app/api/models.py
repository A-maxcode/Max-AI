from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import CurrentUser
from app.services.model_manager import get_model_status


router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def available_models(
    _user: CurrentUser,
) -> JSONResponse:
    result: dict[str, Any] = await get_model_status()
    status_code = 200 if result["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=result)
