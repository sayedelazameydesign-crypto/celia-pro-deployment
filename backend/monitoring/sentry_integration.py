"""
celia.pro Sentry Integration
=============================
Optional Sentry error tracking for production.

Sentry is activated ONLY when SENTRY_DSN environment variable is set.
If DSN is not provided, Sentry is silently disabled (no impact on tests/dev).

Features:
- Automatic error capture from FastAPI
- Request context (URL, method, user)
- Performance tracing (optional)
- Breadcrumb logging for debugging

Environment variables:
- SENTRY_DSN: Sentry DSN URL (required to enable)
- SENTRY_ENVIRONMENT: Environment name (default: "production")
- SENTRY_TRACES_SAMPLE_RATE: Trace sampling rate (default: 0.1 = 10%)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Track Sentry state
_sentry_enabled = False


def is_sentry_enabled() -> bool:
    """Check if Sentry is currently enabled."""
    return _sentry_enabled


def setup_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    traces_sample_rate: Optional[float] = None,
) -> bool:
    """
    Initialize Sentry error tracking.
    
    Sentry is only activated if a valid DSN is provided (via parameter
    or SENTRY_DSN environment variable).
    
    Args:
        dsn: Sentry DSN URL. Falls back to SENTRY_DSN env var.
        environment: Environment name. Falls back to SENTRY_ENVIRONMENT env var.
        traces_sample_rate: Performance tracing rate (0.0 to 1.0).
            Falls back to SENTRY_TRACES_SAMPLE_RATE env var (default: 0.1).
    
    Returns:
        bool: True if Sentry was successfully initialized, False otherwise.
    """
    global _sentry_enabled

    # Resolve DSN
    sentry_dsn = dsn or os.getenv("SENTRY_DSN", "")

    if not sentry_dsn:
        logger.info("Sentry DSN not provided - error tracking disabled")
        _sentry_enabled = False
        return False

    # Resolve environment
    sentry_env = environment or os.getenv("SENTRY_ENVIRONMENT", "production")

    # Resolve traces sample rate
    if traces_sample_rate is None:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=sentry_env,
            release=os.getenv("RELEASE_VERSION", "3.2.0"),
            # Performance monitoring
            traces_sample_rate=traces_sample_rate,
            # Integrations
            integrations=[
                StarletteIntegration(
                    transaction_style="endpoint",
                ),
                FastApiIntegration(
                    transaction_style="endpoint",
                ),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            # Don't send PII by default
            send_default_pii=False,
            # Attach stack traces to non-error events
            attach_stacktrace=True,
            # Max breadcrumbs for debugging
            max_breadcrumbs=50,
        )

        _sentry_enabled = True
        logger.info(
            f"Sentry initialized: environment={sentry_env}, "
            f"traces_sample_rate={traces_sample_rate}"
        )
        return True

    except ImportError:
        logger.warning(
            "sentry-sdk not installed - error tracking disabled. "
            "Install with: pip install sentry-sdk[fastapi]"
        )
        _sentry_enabled = False
        return False

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        _sentry_enabled = False
        return False


def capture_error(error: Exception, **context) -> Optional[str]:
    """
    Capture an error to Sentry if enabled.
    
    Args:
        error: The exception to capture
        **context: Additional context to attach
    
    Returns:
        str: Sentry event ID if captured, None otherwise
    """
    if not _sentry_enabled:
        return None

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            event_id = sentry_sdk.capture_exception(error)

        return event_id

    except Exception as e:
        logger.warning(f"Failed to capture error in Sentry: {e}")
        return None


def add_breadcrumb(message: str, category: str = "app", level: str = "info", **data) -> None:
    """
    Add a breadcrumb for debugging context.
    
    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Log level (debug, info, warning, error)
        **data: Additional data to attach
    """
    if not _sentry_enabled:
        return

    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
        )
    except Exception:
        pass  # Silently ignore breadcrumb errors
