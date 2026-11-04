import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import CurrentUser
from app.core.rate_limit import rate_limiter
from app.core.security import create_session_token, hash_password, hash_session_token, verify_password
from app.database.connection import get_db_session
from app.database.models import AuthSession, User, UserSettings
from app.schemas.auth import AuthResponse, Credentials, UserResponse


router = APIRouter(prefix="/auth", tags=["authentication"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def _set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    settings = get_settings()
    max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        expires=expires_at,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/api",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/api",
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )


async def _check_auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    await rate_limiter.check(
        request,
        scope=request.url.path,
        limit=settings.auth_rate_limit,
        window_seconds=60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: Credentials,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> AuthResponse:
    if not get_settings().allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account registration is disabled.",
        )
    await _check_auth_rate_limit(request)
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(email=str(payload.email), password_hash=password_hash)
    session.add(user)
    token = create_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().access_token_expire_minutes
    )
    try:
        await session.flush()
        session.add(UserSettings(user_id=user.id))
        session.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=expires_at,
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    _set_session_cookie(response, token, expires_at)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: Credentials,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> AuthResponse:
    await _check_auth_rate_limit(request)
    user = await session.scalar(select(User).where(User.email == str(payload.email)))
    password_matches = (
        await asyncio.to_thread(verify_password, payload.password, user.password_hash)
        if user is not None
        else False
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().access_token_expire_minutes
    )
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )
    )
    await session.commit()
    _set_session_cookie(response, token, expires_at)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> Response:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        auth_session = await session.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(timezone.utc)
            await session.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
