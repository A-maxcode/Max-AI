from contextlib import asynccontextmanager
import logging
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api import auth, chat, health, models
from app.config import get_settings
from app.database.connection import engine


settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    yield
    await engine.dispose()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
            )
        if settings.app_env == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


app = FastAPI(
    title=settings.app_name,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    lifespan=lifespan,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(health.router)
api_router.include_router(models.router)
app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1", include_in_schema=False)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database operation failed (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is temporarily unavailable."},
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
