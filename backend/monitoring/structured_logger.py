"""
celia.pro Structured Logger
============================
JSON-formatted structured logging using structlog.

Features:
- JSON output format (machine-parseable)
- Request ID tracking (for distributed tracing)
- User ID context injection
- Timestamps in ISO 8601 format
- Sensitive data redaction (API keys, tokens, passwords)
- Log level filtering

Usage:
    from monitoring.structured_logger import MonitoringLogger
    
    logger = MonitoringLogger.get_logger("my_module")
    logger.info("processing_request", request_id="abc", user_id="user1")
    logger.error("llm_error", provider="gemini", error="timeout")
"""

import sys
import logging
from typing import Optional, Any
import structlog
from structlog.types import Processor


# ============= SENSITIVE KEY REDACTION =============

SENSITIVE_KEYS = frozenset({
    "api_key", "token", "password", "secret", "authorization",
    "hf_token", "groq_key", "gemini_key", "jwt", "bearer",
    "private_key", "access_token", "refresh_token",
})


def redact_sensitive_keys(logger: Any, method_name: str, event_dict: dict) -> dict:
    """
    Redact sensitive keys from log events.
    
    Replaces values of keys matching SENSITIVE_KEYS with "***REDACTED***".
    """
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], str) and key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def add_log_level_name(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Ensure log level is always present."""
    if "level" not in event_dict:
        event_dict["level"] = method_name.upper()
    return event_dict


# ============= SETUP =============

def setup_structured_logging(
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON. If False, output colored console format.
    """
    # Build shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_log_level_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        redact_sensitive_keys,
    ]

    # Output formatter
    if json_output:
        output_processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        output_processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=output_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)
    
    # Set up stdlib handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level_int)
    
    if json_output:
        handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level_int)


# ============= MONITORING LOGGER =============

class MonitoringLogger:
    """
    High-level logging interface for celia.pro.
    
    Provides convenience methods for common logging patterns
    with automatic context injection (request_id, user_id).
    
    Usage:
        logger = MonitoringLogger.get_logger("api.chat")
        logger.info("chat_started", user_id="user123")
        logger.error("llm_failed", provider="gemini", error="timeout")
    """

    @staticmethod
    def get_logger(name: str) -> structlog.stdlib.BoundLogger:
        """
        Get a structured logger instance.
        
        Args:
            name: Logger name (usually module path)
        
        Returns:
            Bound structlog logger
        """
        return structlog.get_logger(name)

    @staticmethod
    def bind_context(**kwargs) -> None:
        """
        Bind context variables that will be included in all subsequent logs.
        
        Typically used at request start:
            MonitoringLogger.bind_context(request_id="abc123", user_id="user456")
        """
        structlog.contextvars.bind_contextvars(**kwargs)

    @staticmethod
    def clear_context() -> None:
        """
        Clear all bound context variables.
        
        Typically used at request end.
        """
        structlog.contextvars.clear_contextvars()

    @staticmethod
    def log_http_request(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: str,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        """
        Log an HTTP request with standard fields.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            request_id: Unique request identifier
            user_id: Authenticated user ID (if available)
            client_ip: Client IP address
        """
        logger = structlog.get_logger("http.request")
        logger.info(
            "request_completed",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
            user_id=user_id or "anonymous",
            client_ip=client_ip or "unknown",
        )

    @staticmethod
    def log_llm_call(
        provider: str,
        model: str,
        duration_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log an LLM API call.
        
        Args:
            provider: LLM provider name (gemini, groq, huggingface)
            model: Model name
            duration_ms: Call duration in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            success: Whether the call succeeded
            error: Error message if failed
        """
        logger = structlog.get_logger("llm.call")
        log_data = {
            "provider": provider,
            "model": model,
            "duration_ms": round(duration_ms, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "success": success,
        }
        if error:
            log_data["error"] = error
            logger.warning("llm_call_failed", **log_data)
        else:
            logger.info("llm_call_completed", **log_data)

    @staticmethod
    def log_tool_execution(
        tool_name: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log a tool execution.
        
        Args:
            tool_name: Name of the tool executed
            duration_ms: Execution duration in milliseconds
            success: Whether execution succeeded
            error: Error message if failed
        """
        logger = structlog.get_logger("tool.execution")
        log_data = {
            "tool_name": tool_name,
            "duration_ms": round(duration_ms, 2),
            "success": success,
        }
        if error:
            log_data["error"] = error
            logger.warning("tool_execution_failed", **log_data)
        else:
            logger.info("tool_executed", **log_data)

    @staticmethod
    def log_error(
        error_type: str,
        message: str,
        category: str = "general",
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **extra,
    ) -> None:
        """
        Log an error with structured context.
        
        Args:
            error_type: Type of error (e.g., "ValidationError", "DatabaseError")
            message: Error message
            category: Error category for grouping
            request_id: Request ID for tracing
            user_id: User ID for context
            **extra: Additional structured fields
        """
        logger = structlog.get_logger("error")
        logger.error(
            "error_occurred",
            error_type=error_type,
            message=message,
            category=category,
            request_id=request_id,
            user_id=user_id,
            **extra,
        )
