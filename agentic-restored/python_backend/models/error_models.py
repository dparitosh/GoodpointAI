"""
Unified API Error Response Models

Standardizes error responses across all routers for consistent client error handling.
"""

from enum import Enum
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ErrorCode(str, Enum):
    """Standard error codes for API errors."""
    
    # 4xx Client Errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    
    # 5xx Server Errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


class ErrorDetail(BaseModel):
    """Detailed error information."""
    
    field: Optional[str] = Field(None, description="Field name if validation error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Specific error code")


class APIErrorResponse(BaseModel):
    """Standard API error response format."""
    
    status_code: int = Field(..., description="HTTP status code")
    error_code: ErrorCode = Field(..., description="Standard error code")
    message: str = Field(..., description="Main error message")
    details: Optional[list[ErrorDetail]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    path: Optional[str] = Field(None, description="Request path")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# ============================================================
# Error Response Builders
# ============================================================

class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        details: Optional[list[ErrorDetail]] = None,
        request_id: Optional[str] = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or []
        self.request_id = request_id
        super().__init__(message)
    
    def to_response(self, path: Optional[str] = None) -> APIErrorResponse:
        """Convert exception to response model."""
        return APIErrorResponse(
            status_code=self.status_code,
            error_code=self.error_code,
            message=self.message,
            details=self.details if self.details else None,
            request_id=self.request_id,
            path=path
        )


class ValidationError(APIError):
    """Validation error (400 Bad Request)."""
    
    def __init__(
        self,
        message: str,
        details: Optional[list[ErrorDetail]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.VALIDATION_ERROR,
            message=message,
            details=details,
            request_id=request_id
        )


class ResourceNotFoundError(APIError):
    """Resource not found error (404 Not Found)."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(
            status_code=404,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
            request_id=request_id
        )


class ResourceAlreadyExistsError(APIError):
    """Resource already exists error (409 Conflict)."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=409,
            error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
            message=f"{resource_type} '{resource_id}' already exists",
            request_id=request_id
        )


class InvalidRequestError(APIError):
    """Invalid request error (400 Bad Request)."""
    
    def __init__(
        self,
        message: str,
        details: Optional[list[ErrorDetail]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.INVALID_REQUEST,
            message=message,
            details=details,
            request_id=request_id
        )


class ConflictError(APIError):
    """Conflict error (409 Conflict)."""
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=409,
            error_code=ErrorCode.CONFLICT,
            message=message,
            request_id=request_id
        )


class DependencyError(APIError):
    """Dependency or prerequisite error (400 Bad Request)."""
    
    def __init__(
        self,
        message: str,
        details: Optional[list[ErrorDetail]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.DEPENDENCY_ERROR,
            message=message,
            details=details,
            request_id=request_id
        )


class DatabaseError(APIError):
    """Database error (500 Internal Server Error)."""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=500,
            error_code=ErrorCode.DATABASE_ERROR,
            message=message,
            request_id=request_id
        )


class ExternalServiceError(APIError):
    """External service error (502 Bad Gateway)."""
    
    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        full_message = f"External service error: {service_name}"
        if message:
            full_message += f" - {message}"
        super().__init__(
            status_code=502,
            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            message=full_message,
            request_id=request_id
        )


class InternalServerError(APIError):
    """Internal server error (500 Internal Server Error)."""
    
    def __init__(
        self,
        message: str = "Internal server error",
        request_id: Optional[str] = None
    ):
        super().__init__(
            status_code=500,
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
            request_id=request_id
        )
