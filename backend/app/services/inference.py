import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.schemas.chat import ChatMessageInput


logger = logging.getLogger(__name__)


async def generate_reply(messages: list[ChatMessageInput]) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": settings.model_system_prompt},
            *[message.model_dump() for message in messages],
        ],
        "max_tokens": settings.model_max_tokens,
        "temperature": settings.model_temperature,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            model_name = settings.model_name
            if model_name == "auto":
                model_response = await client.get(
                    f"{settings.model_server_url}/v1/models"
                )
                model_response.raise_for_status()
                model_data = model_response.json()
                if not isinstance(model_data, dict):
                    raise ValueError("The local model server returned invalid model data.")
                available_models = model_data.get("data", [])
                if (
                    not isinstance(available_models, list)
                    or not available_models
                    or not isinstance(available_models[0], dict)
                    or not isinstance(available_models[0].get("id"), str)
                ):
                    raise ValueError("The local model server did not report a model.")
                model_name = available_models[0]["id"]
            payload["model"] = model_name
            response = await client.post(
                f"{settings.model_server_url}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.TimeoutException as exc:
        logger.warning("llama.cpp inference request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The local model took too long to respond.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("llama.cpp returned HTTP %s", exc.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model could not complete the request.",
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("llama.cpp is unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local model server is unavailable.",
        ) from exc
    except ValueError as exc:
        logger.warning("llama.cpp returned invalid JSON")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model returned an invalid response.",
        ) from exc

    try:
        reply = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model response did not contain a reply.",
        ) from exc
    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model returned an empty reply.",
        )
    return reply.strip()
