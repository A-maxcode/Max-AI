from typing import Any

import httpx

from app.config import get_settings


async def get_model_status() -> dict[str, Any]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            health = await client.get(f"{settings.model_server_url}/health")
            health.raise_for_status()
            response = await client.get(f"{settings.model_server_url}/v1/models")
            response.raise_for_status()
            result = response.json()
    except httpx.TimeoutException:
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": "The local model server timed out.",
            "available_models": [],
        }
    except httpx.HTTPStatusError as exc:
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": f"The local model server returned HTTP {exc.response.status_code}.",
            "available_models": [],
        }
    except httpx.RequestError:
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": "The local model server is unavailable.",
            "available_models": [],
        }
    except ValueError:
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": "The local model server returned invalid model information.",
            "available_models": [],
        }

    try:
        models = result["data"]
        model_ids = [
            model["id"]
            for model in models
            if isinstance(model, dict) and isinstance(model.get("id"), str)
        ]
    except (KeyError, TypeError):
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": "The local model server returned invalid model information.",
            "available_models": [],
        }

    if not model_ids:
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": "The local model server has no loaded models.",
            "available_models": [],
        }
    if settings.model_name != "auto" and settings.model_name not in model_ids:
        return {
            "status": "unavailable",
            "model": settings.model_name,
            "detail": "The configured model is not loaded by the local model server.",
            "available_models": model_ids,
        }

    return {
        "status": "ok",
        "model": model_ids[0] if settings.model_name == "auto" else settings.model_name,
        "available_models": model_ids,
    }
