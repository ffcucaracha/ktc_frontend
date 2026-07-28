from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def api_error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
        },
    )


async def handle_api_error(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, ApiError):
        raise exc
    return api_error_response(exc)


def configure_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, handle_api_error)
