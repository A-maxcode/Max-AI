import httpx
from fastapi import HTTPException

from app.config import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    AI_SYSTEM_PROMPT,
    AI_TIMEOUT_SECONDS,
)
from app.schemas import ChatMessage


async def generate_reply(messages: list[ChatMessage]) -> str:
    if not AI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI provider is not configured. Set AI_API_KEY on the server.",
        )

    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            *[message.model_dump() for message in messages],
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="The AI provider took too long to respond.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"The AI provider returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the AI provider.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an invalid response.",
        ) from exc

    try:
        reply = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="The AI provider response did not contain a reply.",
        ) from exc

    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an empty reply.",
        )
    return reply.strip()
