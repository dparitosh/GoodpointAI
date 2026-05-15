"""
Shared API Response Models
==========================

Centralized Pydantic models for all API responses.
Eliminates duplication of response envelopes across 45+ routers.
Provides consistent structure for success/error/pagination responses.
"""

from typing import Optional, Any, List, Generic, TypeVar, Dict
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================
# GENERIC BASE RESPONSES
# ============================================================

T = TypeVar('T')


class BaseResponse(BaseModel):
    """Base response structure for all API endpoints."""
    
    status: str = Field(..., description="Response status: success, error, etc.")
    message: str = Field(..., description="Human-readable message")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp"
    )
    code: Optional[str] = Field(None, description="Machine-readable code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Operation completed successfully",
                "timestamp": "2026-05-15T10:30:00.000000",
                "code": "OK"
            }
        }


class SuccessResponse(BaseResponse):
    """Standard success response."""
    
    status: str = Field(default="success", description="Always 'success'")
    data: Optional[Any] = Field(None, description="Response payload")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Operation completed successfully",
                "timestamp": "2026-05-15T10:30:00.000000",
                "code": "OK",
                "data": {}
            }
        }


class ErrorResponse(BaseResponse):
    """Standard error response."""
    
    status: str = Field(default="error", description="Always 'error'")
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "Operation failed",
                "timestamp": "2026-05-15T10:30:00.000000",
                "code": "VALIDATION_ERROR",
                "details": {"field": "email", "reason": "Invalid email format"}
            }
        }


# ============================================================
# PAGINATED RESPONSES
# ============================================================

class PaginationMeta(BaseModel):
    """Pagination metadata."""
    
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total items across all pages")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated response with metadata."""
    
    status: str = Field(default="success", description="Always 'success'")
    data: List[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Items retrieved successfully",
                "timestamp": "2026-05-15T10:30:00.000000",
                "data": [],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_items": 100,
                    "total_pages": 5,
                    "has_next": True,
                    "has_previous": False
                }
            }
        }


# ============================================================
# CRUD OPERATION RESPONSES
# ============================================================

class CreatedResponse(BaseResponse):
    """Response for resource creation."""
    
    status: str = Field(default="success", description="Always 'success'")
    resource_id: str = Field(..., description="ID of created resource")
    data: Optional[Any] = Field(None, description="Created resource data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Resource created successfully",
                "timestamp": "2026-05-15T10:30:00.000000",
                "resource_id": "res-12345",
                "data": {}
            }
        }


class UpdatedResponse(BaseResponse):
    """Response for resource update."""
    
    status: str = Field(default="success", description="Always 'success'")
    data: Optional[Any] = Field(None, description="Updated resource data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Resource updated successfully",
                "timestamp": "2026-05-15T10:30:00.000000",
                "data": {}
            }
        }


class DeletedResponse(BaseResponse):
    """Response for resource deletion."""
    
    status: str = Field(default="success", description="Always 'success'")
    resource_id: Optional[str] = Field(None, description="ID of deleted resource")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Resource deleted successfully",
                "timestamp": "2026-05-15T10:30:00.000000",
                "resource_id": "res-12345"
            }
        }


# ============================================================
# VALIDATION & TESTING RESPONSES
# ============================================================

class ValidationResult(BaseModel):
    """Result of validation operation."""
    
    valid: bool = Field(..., description="Whether validation passed")
    errors: Optional[Dict[str, List[str]]] = Field(None, description="Field validation errors")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings")


class ValidationResponse(BaseResponse):
    """Response from validation endpoint."""
    
    status: str = Field(default="success", description="'success' or 'error'")
    result: ValidationResult = Field(..., description="Validation result")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Validation completed",
                "timestamp": "2026-05-15T10:30:00.000000",
                "result": {
                    "valid": True,
                    "errors": None,
                    "warnings": None
                }
            }
        }


class ConnectionTestResult(BaseModel):
    """Result of connection test."""
    
    connected: bool = Field(..., description="Whether connection succeeded")
    message: str = Field(..., description="Connection result message")
    error_type: Optional[str] = Field(None, description="Type of error if failed")
    error_message: Optional[str] = Field(None, description="Detailed error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class ConnectionTestResponse(BaseResponse):
    """Response from connection test endpoint."""
    
    status: str = Field(default="success", description="'success' or 'error'")
    result: ConnectionTestResult = Field(..., description="Connection test result")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Connection test completed",
                "timestamp": "2026-05-15T10:30:00.000000",
                "result": {
                    "connected": True,
                    "message": "Connection successful",
                    "error_type": None,
                    "error_message": None,
                    "details": {}
                }
            }
        }


# ============================================================
# BATCH OPERATION RESPONSES
# ============================================================

class BatchItemResult(BaseModel):
    """Result for single item in batch operation."""
    
    item_id: str = Field(..., description="Item identifier")
    status: str = Field(..., description="Item status: success, error, skipped")
    message: str = Field(..., description="Result message")
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchOperationResponse(BaseResponse):
    """Response from batch operation endpoint."""
    
    status: str = Field(default="success", description="Overall status")
    results: List[BatchItemResult] = Field(..., description="Per-item results")
    summary: Dict[str, int] = Field(..., description="Summary counts: success, error, skipped")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Batch operation completed",
                "timestamp": "2026-05-15T10:30:00.000000",
                "results": [
                    {
                        "item_id": "item-1",
                        "status": "success",
                        "message": "Item processed"
                    }
                ],
                "summary": {
                    "success": 1,
                    "error": 0,
                    "skipped": 0
                }
            }
        }


# ============================================================
# ASYNC OPERATION RESPONSES
# ============================================================

class AsyncOperationStatus(BaseModel):
    """Status of async operation."""
    
    operation_id: str = Field(..., description="Unique operation ID")
    status: str = Field(..., description="Status: pending, running, completed, failed")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    result: Optional[Any] = Field(None, description="Result if completed")
    created_at: str = Field(..., description="Operation creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class AsyncOperationResponse(BaseResponse):
    """Response for async operation endpoints."""
    
    status: str = Field(default="success", description="API response status")
    operation: AsyncOperationStatus = Field(..., description="Operation status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Operation status retrieved",
                "timestamp": "2026-05-15T10:30:00.000000",
                "operation": {
                    "operation_id": "op-12345",
                    "status": "running",
                    "progress": 50.0,
                    "message": "Processing items...",
                    "created_at": "2026-05-15T10:00:00.000000",
                    "updated_at": "2026-05-15T10:30:00.000000"
                }
            }
        }


# ============================================================
# HEALTH CHECK RESPONSE
# ============================================================

class DependencyStatus(BaseModel):
    """Status of a system dependency."""
    
    name: str = Field(..., description="Dependency name")
    status: str = Field(..., description="Status: healthy, degraded, unhealthy")
    message: Optional[str] = Field(None, description="Status message")
    version: Optional[str] = Field(None, description="Dependency version")


class HealthCheckResponse(BaseResponse):
    """Response from health check endpoint."""
    
    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    dependencies: Dict[str, DependencyStatus] = Field(..., description="Dependency statuses")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "All systems operational",
                "timestamp": "2026-05-15T10:30:00.000000",
                "dependencies": {
                    "postgres": {
                        "name": "PostgreSQL",
                        "status": "healthy",
                        "message": "Connected",
                        "version": "14.5"
                    }
                },
                "uptime_seconds": 86400.0
            }
        }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def make_success_response(
    message: str = "Success",
    data: Optional[Any] = None,
    code: str = "OK"
) -> SuccessResponse:
    """Create a success response."""
    return SuccessResponse(
        status="success",
        message=message,
        code=code,
        data=data,
        timestamp=datetime.utcnow().isoformat()
    )


def make_error_response(
    message: str = "Error",
    code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None
) -> ErrorResponse:
    """Create an error response."""
    return ErrorResponse(
        status="error",
        message=message,
        code=code,
        details=details,
        timestamp=datetime.utcnow().isoformat()
    )


def make_created_response(
    resource_id: str,
    message: str = "Resource created successfully",
    data: Optional[Any] = None
) -> CreatedResponse:
    """Create a creation response."""
    return CreatedResponse(
        status="success",
        message=message,
        resource_id=resource_id,
        data=data,
        timestamp=datetime.utcnow().isoformat()
    )


def make_paginated_response(
    items: List[Any],
    page: int,
    page_size: int,
    total_items: int,
    message: str = "Items retrieved successfully"
) -> PaginatedResponse:
    """Create a paginated response."""
    total_pages = (total_items + page_size - 1) // page_size
    
    return PaginatedResponse(
        status="success",
        message=message,
        data=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        ),
        timestamp=datetime.utcnow().isoformat()
    )
