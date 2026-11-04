from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.security import create_session_token, hash_session_token
from app.database.models import AuthSession, User


@pytest.mark.asyncio
async def test_registration_hashes_password_and_sets_http_only_cookie(client, database):
    response = await client.post(
        "/api/auth/register",
        json={"email": "Person@Example.com", "password": "a-very-long-test-password"},
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "person@example.com"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    async with database() as session:
        user = await session.scalar(select(User).where(User.email == "person@example.com"))
        assert user is not None
        assert user.password_hash != "a-very-long-test-password"
        assert user.password_hash.startswith("$argon2")


@pytest.mark.asyncio
async def test_duplicate_registration_and_invalid_input_are_rejected(client):
    credentials = {"email": "person@example.com", "password": "a-very-long-test-password"}
    assert (await client.post("/api/auth/register", json=credentials)).status_code == 201
    assert (await client.post("/api/auth/register", json=credentials)).status_code == 409
    assert (
        await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "short"},
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_registration_can_be_disabled(client, monkeypatch):
    settings = get_settings().model_copy(update={"allow_registration": False})
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)

    response = await client.post(
        "/api/auth/register",
        json={"email": "closed@example.com", "password": "a-very-long-test-password"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_and_invalid_credentials(client):
    credentials = {"email": "person@example.com", "password": "a-very-long-test-password"}
    await client.post("/api/auth/register", json=credentials)
    await client.post("/api/auth/logout")

    success = await client.post("/api/auth/login", json=credentials)
    invalid = await client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": "a-different-long-password"},
    )

    assert success.status_code == 200
    assert invalid.status_code == 401
    assert invalid.json() == {"detail": "Invalid email or password."}


@pytest.mark.asyncio
async def test_revoked_and_expired_sessions_are_rejected(client, database):
    credentials = {"email": "person@example.com", "password": "a-very-long-test-password"}
    await client.post("/api/auth/register", json=credentials)
    token = client.cookies.get(get_settings().session_cookie_name)
    await client.post("/api/auth/logout")
    client.cookies.set(get_settings().session_cookie_name, token)
    assert (await client.get("/api/auth/me")).status_code == 401

    async with database() as session:
        user = await session.scalar(select(User).where(User.email == credentials["email"]))
        expired_token = create_session_token()
        session.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_session_token(expired_token),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    client.cookies.set(get_settings().session_cookie_name, expired_token)
    assert (await client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_protected_routes_require_login(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/models")).status_code == 401
    assert (await client.get("/api/conversations")).status_code == 401
    response = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 401
