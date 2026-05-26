import logging
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from models.error_models import (
    APIError,
    InternalServerError,
    ValidationError,
    ErrorDetail,
)

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    """Extract or generate request ID."""
    existing = request.headers.get("x-request-id")
    return existing or str(uuid.uuid4())


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors with standardized response format."""
    request_id = _request_id(request)
    exc.request_id = request_id
    response = exc.to_response(path=str(request.url.path))
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True)
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    request_id = _request_id(request)
    if isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        status_code = 500
        detail = "Internal Server Error"
    
    # Convert to standardized error response
    if status_code == 404:
        error_code = "RESOURCE_NOT_FOUND"
    elif status_code == 409:
        error_code = "CONFLICT"
    elif status_code == 400:
        error_code = "INVALID_REQUEST"
    elif status_code >= 500:
        error_code = "INTERNAL_SERVER_ERROR"
    else:
        error_code = "INVALID_REQUEST"
    
    payload = {
        "status_code": status_code,
        "error_code": error_code,
        "message": detail if isinstance(detail, str) else "Request failed",
        "request_id": request_id,
        "path": str(request.url.path),
    }
    return JSONResponse(status_code=status_code, content=payload)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle validation errors with detailed error information."""
    request_id = _request_id(request)
    
    # Extract validation errors
    errors = []
    if isinstance(exc, RequestValidationError):
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error.get("loc", [])[1:])
            errors.append({
                "field": field,
                "message": error.get("msg", "Validation failed"),
                "code": error.get("type"),
            })
    
    # Create validation error response
    validation_err = ValidationError(
        message="Request validation failed",
        details=[
            ErrorDetail(
                field=err.get("field"),
                message=err.get("message"),
                code=err.get("code")
            )
            for err in errors
        ],
        request_id=request_id
    )
    
    response = validation_err.to_response(path=str(request.url.path))
    return JSONResponse(
        status_code=422,
        content=response.model_dump(exclude_none=True)
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with logging."""
    request_id = _request_id(request)
    logger.exception("Unhandled exception (request_id=%s): %s", request_id, exc)
    
    # Create internal server error response
    error = InternalServerError(
        message="An unexpected error occurred. Please contact support.",
        request_id=request_id
    )
    
    response = error.to_response(path=str(request.url.path))
    return JSONResponse(
        status_code=500,
        content=response.model_dump(exclude_none=True)
    )
