import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_rejects_requests_over_configured_limit():
    limiter = InMemoryRateLimiter()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [],
            "client": ("192.0.2.10", 12345),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )

    await limiter.check(request, scope="login", limit=1)
    with pytest.raises(HTTPException) as caught:
        await limiter.check(request, scope="login", limit=1)

    assert caught.value.status_code == 429
    assert any(name.lower() == "retry-after" for name in caught.value.headers)
