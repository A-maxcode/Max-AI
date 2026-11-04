from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_health_checks_database_and_serves_frontend(client):
    health = await client.get("/api/health")
    page = await client.get("/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "ok"}
    assert "default-src 'self'" in health.headers["content-security-policy"]
    assert page.status_code == 200
    assert "Max-AI" in page.text
    versioned_health = await client.get("/api/v1/health")
    assert versioned_health.status_code == 200


@pytest.mark.asyncio
async def test_model_health_reports_unavailable_without_model(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.health.get_model_status",
        AsyncMock(
            return_value={
                "status": "unavailable",
                "model": "test-model",
                "detail": "The local model server is unavailable.",
                "available_models": [],
            }
        ),
    )

    response = await client.get("/api/health/model")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


@pytest.mark.asyncio
async def test_model_health_reports_loaded_model(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.health.get_model_status",
        AsyncMock(
            return_value={
                "status": "ok",
                "model": "qwen-local",
                "available_models": ["qwen-local"],
            }
        ),
    )

    response = await client.get("/api/health/model")

    assert response.status_code == 200
    assert response.json()["available_models"] == ["qwen-local"]


@pytest.mark.asyncio
async def test_cors_is_restricted_to_configured_origin(client):
    allowed = await client.options(
        "/api/health",
        headers={
            "Origin": "http://test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = await client.options(
        "/api/health",
        headers={
            "Origin": "https://not-allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers.get("access-control-allow-origin") == "http://test"
    assert denied.headers.get("access-control-allow-origin") is None
