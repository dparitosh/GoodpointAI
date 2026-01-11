import logging
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id")
    return existing or str(uuid.uuid4())


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    if isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        status_code = 500
        detail = "Internal Server Error"
    payload = {
        "error": {
            "message": detail if isinstance(detail, str) else "Request failed",
            "type": "http_error",
            "status_code": status_code,
            "request_id": request_id,
        },
        "detail": detail,
    }
    return JSONResponse(status_code=status_code, content=payload)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    payload = {
        "error": {
            "message": "Validation error",
            "type": "validation_error",
            "status_code": 422,
            "request_id": request_id,
        },
        "detail": errors,
    }
    return JSONResponse(status_code=422, content=payload)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.exception("Unhandled error (request_id=%s): %s", request_id, exc)
    payload = {
        "error": {
            "message": "Internal Server Error",
            "type": "internal_error",
            "status_code": 500,
            "request_id": request_id,
        },
        "detail": "Internal Server Error",
    }
    return JSONResponse(status_code=500, content=payload)
