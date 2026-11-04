import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite+aiosqlite://",
        "MODEL_SERVER_URL": "http://127.0.0.1:9",
        "FRONTEND_ORIGINS": "http://test",
        "AUTH_RATE_LIMIT": "100",
        "CHAT_RATE_LIMIT": "100",
    }
)

from app.core.rate_limit import rate_limiter
from app.database.connection import get_db_session
from app.database.models import Base
from app.main import app


@pytest_asyncio.fixture
async def database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(database: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def override_database() -> AsyncIterator[AsyncSession]:
        async with database() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_database
    await rate_limiter.reset()
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    app.dependency_overrides.clear()
    await rate_limiter.reset()
