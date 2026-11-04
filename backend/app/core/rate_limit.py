import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Single-process limiter; put a shared limiter at the edge for multiple workers."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(
        self,
        request: Request,
        *,
        scope: str,
        limit: int,
        window_seconds: int = 60,
    ) -> None:
        client_host = request.client.host if request.client else "unknown"
        key = (scope, client_host)
        now = time.monotonic()
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)
            if len(self._events) > 10_000:
                self._events = defaultdict(
                    deque,
                    {
                        bucket: timestamps
                        for bucket, timestamps in self._events.items()
                        if timestamps and timestamps[-1] > now - window_seconds
                    },
                )

    async def reset(self) -> None:
        async with self._lock:
            self._events.clear()


rate_limiter = InMemoryRateLimiter()
