"""
celia.pro Prometheus Metrics
=============================
Configures Prometheus metrics for the FastAPI application.
Exposes /metrics endpoint for scraping.

Metrics collected:
- HTTP request count (by method, endpoint, status)
- HTTP request duration (histogram)
- Request size (histogram)
- Response size (histogram)
- Custom business metrics (LLM calls, tool executions, etc.)
"""

import time
from typing import Optional
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import Info as InstrumentatorInfo
from fastapi import FastAPI, Response


# ============= REGISTRY =============

# Use default registry for simplicity
metrics_registry = CollectorRegistry()


# ============= CUSTOM BUSINESS METRICS =============

class PrometheusMetrics:
    """
    Custom Prometheus metrics for celia.pro business logic.
    
    These track domain-specific events beyond standard HTTP metrics:
    - LLM API calls and latencies
    - Tool executions
    - User actions (conversations, messages)
    - Error rates by category
    """

    # --- LLM Metrics ---
    llm_requests_total = Counter(
        "novamind_llm_requests_total",
        "Total number of LLM API requests",
        ["provider", "model", "status"],
        registry=metrics_registry,
    )

    llm_request_duration_seconds = Histogram(
        "novamind_llm_request_duration_seconds",
        "LLM API request duration in seconds",
        ["provider", "model"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
        registry=metrics_registry,
    )

    llm_tokens_total = Counter(
        "novamind_llm_tokens_total",
        "Total number of LLM tokens processed",
        ["provider", "type"],  # type: input or output
        registry=metrics_registry,
    )

    # --- Tool Execution Metrics ---
    tool_executions_total = Counter(
        "novamind_tool_executions_total",
        "Total number of tool executions",
        ["tool_name", "status"],
        registry=metrics_registry,
    )

    tool_execution_duration_seconds = Histogram(
        "novamind_tool_execution_duration_seconds",
        "Tool execution duration in seconds",
        ["tool_name"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        registry=metrics_registry,
    )

    # --- User/Conversation Metrics ---
    active_users_gauge = Gauge(
        "novamind_active_users",
        "Number of currently active users (requests in last 5 minutes)",
        registry=metrics_registry,
    )

    conversations_total = Counter(
        "novamind_conversations_total",
        "Total number of conversations created",
        registry=metrics_registry,
    )

    messages_total = Counter(
        "novamind_messages_total",
        "Total number of messages processed",
        registry=metrics_registry,
    )

    # --- Error Metrics ---
    errors_total = Counter(
        "novamind_errors_total",
        "Total number of errors by category",
        ["error_type", "category"],
        registry=metrics_registry,
    )

    # --- Circuit Breaker Metrics ---
    circuit_breaker_state = Gauge(
        "novamind_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=half_open, 2=open)",
        ["provider"],
        registry=metrics_registry,
    )

    # --- System Info ---
    system_info = Info(
        "novamind_system",
        "celia.pro system information",
        registry=metrics_registry,
    )

    @classmethod
    def record_llm_request(cls, provider: str, model: str, status: str = "success"):
        """Record an LLM API request."""
        cls.llm_requests_total.labels(
            provider=provider, model=model, status=status
        ).inc()

    @classmethod
    def record_llm_duration(cls, provider: str, model: str, duration: float):
        """Record LLM API request duration."""
        cls.llm_request_duration_seconds.labels(
            provider=provider, model=model
        ).observe(duration)

    @classmethod
    def record_llm_tokens(cls, provider: str, token_type: str, count: int):
        """Record LLM token usage."""
        cls.llm_tokens_total.labels(
            provider=provider, type=token_type
        ).inc(count)

    @classmethod
    def record_tool_execution(cls, tool_name: str, status: str = "success"):
        """Record a tool execution."""
        cls.tool_executions_total.labels(
            tool_name=tool_name, status=status
        ).inc()

    @classmethod
    def record_tool_duration(cls, tool_name: str, duration: float):
        """Record tool execution duration."""
        cls.tool_execution_duration_seconds.labels(
            tool_name=tool_name
        ).observe(duration)

    @classmethod
    def record_conversation_created(cls):
        """Record a new conversation."""
        cls.conversations_total.inc()

    @classmethod
    def record_message_processed(cls):
        """Record a processed message."""
        cls.messages_total.inc()

    @classmethod
    def record_error(cls, error_type: str, category: str = "general"):
        """Record an error."""
        cls.errors_total.labels(
            error_type=error_type, category=category
        ).inc()

    @classmethod
    def set_circuit_breaker_state(cls, provider: str, state: str):
        """Set circuit breaker state gauge."""
        state_map = {"closed": 0, "half_open": 1, "open": 2}
        cls.circuit_breaker_state.labels(provider=provider).set(
            state_map.get(state, 0)
        )

    @classmethod
    def set_active_users(cls, count: int):
        """Set active users gauge."""
        cls.active_users_gauge.set(count)

    @classmethod
    def set_system_info(cls, version: str, environment: str = "production"):
        """Set system info labels."""
        cls.system_info.info({
            "version": version,
            "environment": environment,
        })


# ============= CUSTOM INSTRUMENTATION FUNCTION =============

def _custom_metrics(info: InstrumentatorInfo):
    """
    Custom metrics function for prometheus-fastapi-instrumentator.
    Extracts request details and records custom histograms/counters.
    """
    # Track request duration with custom buckets for /api/ endpoints
    if info.request and hasattr(info, 'response'):
        pass  # Default instrumentator handles this


# ============= SETUP FUNCTION =============

def setup_prometheus(app: FastAPI, endpoint: str = "/metrics") -> None:
    """
    Configure Prometheus metrics for the FastAPI application.
    
    Args:
        app: FastAPI application instance
        endpoint: Path for the /metrics endpoint (default: /metrics)
    
    This:
    1. Sets up the prometheus-fastapi-instrumentator with default HTTP metrics
    2. Exposes the /metrics endpoint (no auth required)
    3. Sets system info labels
    """
    # Set system info
    PrometheusMetrics.set_system_info(version="3.2.0", environment="production")

    # Configure instrumentator with standard HTTP metrics
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=[
            "/metrics",          # Don't track metrics endpoint itself
            "/api/ready",        # Don't track readiness probes
            "/api/live",         # Don't track liveness probes
        ],
        should_respect_env_var=False,
        env_var_name="ENABLE_METRICS",
        # Use the default registry to include our custom metrics
        registry=metrics_registry,
    )

    # Instrument the app with default metrics
    instrumentator.instrument(app).expose(
        app,
        endpoint=endpoint,
        should_gzip=False,
        tags=["monitoring"],
    )


def get_metrics_text() -> str:
    """
    Generate Prometheus metrics text in exposition format.
    
    Returns:
        str: Metrics in Prometheus text format
    """
    return generate_latest(metrics_registry).decode("utf-8")
