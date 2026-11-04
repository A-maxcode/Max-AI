from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_session_token
from app.database.connection import get_db_session
from app.database.models import AuthSession, User


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    auth_session = await session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    user = await session.get(User, auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
