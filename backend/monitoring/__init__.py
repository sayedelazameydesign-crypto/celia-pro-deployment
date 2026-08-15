"""
celia.pro Monitoring Module
============================
Production-ready monitoring infrastructure:
- Prometheus metrics (request counting, latency histograms)
- Structured logging (JSON-formatted, request tracking)
- Sentry error tracking (optional, DSN-based)
"""

from monitoring.prometheus_metrics import (
    setup_prometheus,
    PrometheusMetrics,
    metrics_registry,
)
from monitoring.structured_logger import (
    setup_structured_logging,
    MonitoringLogger,
)
from monitoring.sentry_integration import (
    setup_sentry,
    is_sentry_enabled,
)

__all__ = [
    "setup_prometheus",
    "PrometheusMetrics",
    "metrics_registry",
    "setup_structured_logging",
    "MonitoringLogger",
    "setup_sentry",
    "is_sentry_enabled",
]
