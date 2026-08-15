"""
NovaMind Exception Handler
============================
Centralized exception handling with consistent error responses.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# ============= Custom Exceptions =============

class NovaMindException(Exception):
    """Base exception for NovaMind application."""
    
    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(NovaMindException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details
        )
        self.headers = {"WWW-Authenticate": "Bearer"}


class AuthorizationError(NovaMindException):
    """User not authorized for this action."""
    
    def __init__(self, message: str = "Not authorized", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details
        )


class NotFoundError(NovaMindException):
    """Resource not found."""
    
    def __init__(self, resource: str = "Resource", details: Optional[Dict] = None):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=404,
            details=details
        )


class ValidationError(NovaMindException):
    """Validation failed."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        details = details or {}
        if field:
            details["field"] = field
        
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class ToolExecutionError(NovaMindException):
    """Tool execution failed."""
    
    def __init__(self, tool_name: str, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"Tool '{tool_name}' failed: {message}",
            code="TOOL_EXECUTION_ERROR",
            status_code=500,
            details={"tool": tool_name, **(details or {})}
        )


class DatabaseError(NovaMindException):
    """Database operation failed."""
    
    def __init__(self, message: str = "Database operation failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class LLMProviderError(NovaMindException):
    """LLM provider error."""
    
    def __init__(self, provider: str, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"LLM provider '{provider}' error: {message}",
            code="LLM_PROVIDER_ERROR",
            status_code=503,
            details={"provider": provider, **(details or {})}
        )


class RateLimitError(NovaMindException):
    """Rate limit exceeded."""
    
    def __init__(self, retry_after: int = 60, details: Optional[Dict] = None):
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after, **(details or {})}
        )


# ============= Exception Handlers =============

async def novamind_exception_handler(request: Request, exc: NovaMindException):
    """Handle NovaMind custom exceptions."""
    logger.error(
        f"NovaMindException: {exc.code} - {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    headers = getattr(exc, 'headers', None)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        },
        headers=headers
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation error: {len(errors)} errors",
        extra={"path": request.url.path, "errors": errors}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": {"errors": errors}
            }
        }
    )


async def database_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle SQLAlchemy database errors."""
    logger.error(
        f"Database error: {str(exc)}",
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "Database operation failed",
                "details": {"error_type": type(exc).__name__}
            }
        }
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors (unique constraints, etc.)."""
    error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
    
    logger.warning(
        f"Integrity error: {error_msg}",
        extra={"path": request.url.path}
    )
    
    # Try to extract useful information
    details = {}
    if "UNIQUE constraint failed" in error_msg:
        details["constraint"] = "unique"
        message = "A record with this data already exists"
    elif "FOREIGN KEY constraint failed" in error_msg:
        details["constraint"] = "foreign_key"
        message = "Related record not found"
    else:
        message = "Database integrity error"
    
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": {
                "code": "INTEGRITY_ERROR",
                "message": message,
                "details": details
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}",
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {
                    "type": type(exc).__name__,
                    "message": str(exc) if not isinstance(exc, NovaMindException) else None
                }
            }
        }
    )


# ============= Helper Functions =============

def raise_not_found(resource: str = "Resource", **kwargs):
    """Helper to raise NotFoundError."""
    raise NotFoundError(resource, details=kwargs)


def raise_validation_error(message: str, field: Optional[str] = None, **kwargs):
    """Helper to raise ValidationError."""
    raise ValidationError(message, field, details=kwargs)


def raise_authentication_error(message: str = "Authentication failed", **kwargs):
    """Helper to raise AuthenticationError."""
    raise AuthenticationError(message, details=kwargs)


def raise_authorization_error(message: str = "Not authorized", **kwargs):
    """Helper to raise AuthorizationError."""
    raise AuthorizationError(message, details=kwargs)
