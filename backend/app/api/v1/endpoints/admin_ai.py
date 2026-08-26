from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_admin
from app.api.errors import ApiError
from app.core.config import get_settings
from app.models import User

router = APIRouter(prefix="/admin/ai-models", tags=["admin-ai-models"])


@router.get("")
async def list_ai_models(
    admin: Annotated[User, Depends(require_admin)],
) -> list[dict[str, Any]]:
    del admin
    settings = get_settings()
    timeout = httpx.Timeout(
        connect=settings.ai_connect_timeout_seconds,
        read=settings.ai_read_timeout_seconds,
        write=settings.ai_read_timeout_seconds,
        pool=settings.ai_connect_timeout_seconds,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{settings.ai_service_base_url.rstrip('/')}/v1/models")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="AI_MODEL_CATALOG_UNAVAILABLE",
            message="Не удалось получить сведения о сохранённых AI-моделях",
        ) from exc

    payload = response.json()
    if not isinstance(payload, list):
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="AI_MODEL_CATALOG_INVALID",
            message="AI-сервис вернул некорректный каталог моделей",
        )
    return [item for item in payload if isinstance(item, dict)]
