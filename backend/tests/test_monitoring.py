"""
Tests for celia.pro Monitoring Module
======================================
Tests for:
- Prometheus metrics endpoint
- Structured logging (JSON format, request_id tracking)
- Sentry integration (optional, no DSN = disabled)
- System metrics endpoint
"""

import pytest
import pytest_asyncio
import json
import logging
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Test imports
from monitoring.prometheus_metrics import (
    setup_prometheus,
    PrometheusMetrics,
    metrics_registry,
    get_metrics_text,
)
from monitoring.structured_logger import (
    setup_structured_logging,
    MonitoringLogger,
    redact_sensitive_keys,
)
from monitoring.sentry_integration import (
    setup_sentry,
    is_sentry_enabled,
    capture_error,
    add_breadcrumb,
)
from database.connection import get_db


# ============= PROMETHEUS METRICS TESTS =============

class TestPrometheusMetrics:
    """Test Prometheus metrics collection and exposure."""

    def test_metrics_registry_exists(self):
        """Test that the metrics registry is initialized."""
        assert metrics_registry is not None

    def test_get_metrics_text(self):
        """Test that metrics text can be generated."""
        text = get_metrics_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_record_llm_request(self):
        """Test recording an LLM request counter."""
        PrometheusMetrics.record_llm_request(
            provider="gemini", model="gemini-2.0-flash", status="success"
        )
        # Verify metric was recorded (no exception raised)

    def test_record_llm_duration(self):
        """Test recording an LLM request duration."""
        PrometheusMetrics.record_llm_duration(
            provider="gemini", model="gemini-2.0-flash", duration=1.5
        )
        # No exception = success

    def test_record_llm_tokens(self):
        """Test recording token usage."""
        PrometheusMetrics.record_llm_tokens(
            provider="gemini", token_type="input", count=100
        )
        PrometheusMetrics.record_llm_tokens(
            provider="gemini", token_type="output", count=50
        )

    def test_record_tool_execution(self):
        """Test recording tool executions."""
        PrometheusMetrics.record_tool_execution(
            tool_name="web_search", status="success"
        )
        PrometheusMetrics.record_tool_execution(
            tool_name="code_execution", status="error"
        )

    def test_record_tool_duration(self):
        """Test recording tool execution duration."""
        PrometheusMetrics.record_tool_duration(
            tool_name="web_search", duration=0.5
        )

    def test_record_conversation_created(self):
        """Test recording conversation creation."""
        PrometheusMetrics.record_conversation_created()

    def test_record_message_processed(self):
        """Test recording message processing."""
        PrometheusMetrics.record_message_processed()

    def test_record_error(self):
        """Test recording errors by category."""
        PrometheusMetrics.record_error(
            error_type="ValidationError", category="input"
        )
        PrometheusMetrics.record_error(
            error_type="DatabaseError", category="database"
        )

    def test_set_circuit_breaker_state(self):
        """Test setting circuit breaker state."""
        PrometheusMetrics.set_circuit_breaker_state("gemini", "closed")
        PrometheusMetrics.set_circuit_breaker_state("groq", "open")
        PrometheusMetrics.set_circuit_breaker_state("huggingface", "half_open")

    def test_set_active_users(self):
        """Test setting active users gauge."""
        PrometheusMetrics.set_active_users(42)

    def test_set_system_info(self):
        """Test setting system info labels."""
        PrometheusMetrics.set_system_info(
            version="3.2.0", environment="test"
        )

    def test_metrics_text_contains_custom_metrics(self):
        """Test that generated metrics text includes our custom metrics."""
        # First, record some metrics
        PrometheusMetrics.record_llm_request("gemini", "test-model", "success")
        PrometheusMetrics.record_message_processed()

        text = get_metrics_text()
        # Custom metrics should appear in the output
        assert "novamind" in text


# ============= STRUCTURED LOGGING TESTS =============

class TestStructuredLogging:
    """Test structured logging configuration and functionality."""

    def test_setup_structured_logging(self):
        """Test that structured logging can be set up without errors."""
        setup_structured_logging(log_level="INFO", json_output=True)

    def test_setup_structured_logging_console(self):
        """Test console format logging setup."""
        setup_structured_logging(log_level="DEBUG", json_output=False)

    def test_get_logger(self):
        """Test getting a logger instance."""
        logger = MonitoringLogger.get_logger("test.module")
        assert logger is not None

    def test_bind_and_clear_context(self):
        """Test binding and clearing context variables."""
        MonitoringLogger.bind_context(request_id="test-123", user_id="user-456")
        # No exception = success
        MonitoringLogger.clear_context()

    def test_log_http_request(self, caplog):
        """Test HTTP request logging."""
        # Re-setup for this test
        setup_structured_logging(log_level="INFO", json_output=True)
        
        MonitoringLogger.log_http_request(
            method="GET",
            path="/api/health",
            status_code=200,
            duration_ms=15.5,
            request_id="req_test123",
            user_id="user_abc",
            client_ip="127.0.0.1",
        )
        # No exception = success (logging goes to stdout)

    def test_log_llm_call_success(self):
        """Test successful LLM call logging."""
        MonitoringLogger.log_llm_call(
            provider="gemini",
            model="gemini-2.0-flash",
            duration_ms=1200.0,
            input_tokens=100,
            output_tokens=50,
            success=True,
        )

    def test_log_llm_call_failure(self):
        """Test failed LLM call logging."""
        MonitoringLogger.log_llm_call(
            provider="groq",
            model="llama-3.3-70b-versatile",
            duration_ms=5000.0,
            input_tokens=0,
            output_tokens=0,
            success=False,
            error="rate limited",
        )

    def test_log_tool_execution_success(self):
        """Test successful tool execution logging."""
        MonitoringLogger.log_tool_execution(
            tool_name="web_search",
            duration_ms=500.0,
            success=True,
        )

    def test_log_tool_execution_failure(self):
        """Test failed tool execution logging."""
        MonitoringLogger.log_tool_execution(
            tool_name="shell",
            duration_ms=100.0,
            success=False,
            error="command not allowed",
        )

    def test_log_error(self):
        """Test error logging."""
        MonitoringLogger.log_error(
            error_type="DatabaseError",
            message="Connection failed",
            category="database",
            request_id="req_123",
            user_id="user_456",
        )


class TestSensitiveDataRedaction:
    """Test that sensitive data is properly redacted from logs."""

    def test_redact_api_key(self):
        """Test that api_key fields are redacted."""
        event_dict = {"api_key": "secret123", "message": "test"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["api_key"] == "***REDACTED***"
        assert result["message"] == "test"

    def test_redact_token(self):
        """Test that token fields are redacted."""
        event_dict = {"token": "abc123", "provider": "gemini"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["token"] == "***REDACTED***"
        assert result["provider"] == "gemini"

    def test_redact_password(self):
        """Test that password fields are redacted."""
        event_dict = {"password": "mysecret", "username": "admin"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["password"] == "***REDACTED***"
        assert result["username"] == "admin"

    def test_redact_authorization(self):
        """Test that authorization fields are redacted."""
        event_dict = {"authorization": "Bearer token123"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["authorization"] == "***REDACTED***"

    def test_redact_hf_token(self):
        """Test that hf_token fields are redacted."""
        event_dict = {"hf_token": "hf_abc123"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["hf_token"] == "***REDACTED***"

    def test_redact_groq_key(self):
        """Test that groq_key fields are redacted."""
        event_dict = {"groq_key": "gsk_abc123"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["groq_key"] == "***REDACTED***"

    def test_no_redaction_for_normal_fields(self):
        """Test that normal fields are not redacted."""
        event_dict = {"provider": "gemini", "model": "gemini-2.0-flash", "count": 42}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["provider"] == "gemini"
        assert result["model"] == "gemini-2.0-flash"
        assert result["count"] == 42

    def test_case_insensitive_redaction(self):
        """Test that redaction is case-insensitive."""
        event_dict = {"API_KEY": "secret", "Token": "abc"}
        result = redact_sensitive_keys(None, "info", event_dict)
        assert result["API_KEY"] == "***REDACTED***"
        assert result["Token"] == "***REDACTED***"


# ============= SENTRY INTEGRATION TESTS =============

class TestSentryIntegration:
    """Test Sentry integration (without actual DSN)."""

    def test_sentry_disabled_without_dsn(self):
        """Test that Sentry is disabled when no DSN is provided."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SENTRY_DSN", None)
            result = setup_sentry()
            assert result is False
            assert is_sentry_enabled() is False

    def test_sentry_disabled_with_empty_dsn(self):
        """Test that Sentry is disabled with empty DSN."""
        with patch.dict(os.environ, {"SENTRY_DSN": ""}):
            result = setup_sentry()
            assert result is False
            assert is_sentry_enabled() is False

    def test_capture_error_returns_none_when_disabled(self):
        """Test that capture_error returns None when Sentry is disabled."""
        result = capture_error(
            ValueError("test error"), user_id="test-user"
        )
        assert result is None

    def test_add_breadcrumb_no_error_when_disabled(self):
        """Test that add_breadcrumb doesn't error when Sentry is disabled."""
        # Should not raise any exception
        add_breadcrumb(
            message="test message",
            category="test",
            level="info",
        )

    def test_setup_sentry_with_invalid_dsn(self):
        """Test that Sentry handles invalid DSN gracefully."""
        result = setup_sentry(dsn="invalid-dsn-not-a-url")
        # Should fail gracefully (either False or exception caught internally)
        # The important thing is it doesn't crash


# ============= /metrics ENDPOINT TESTS =============

class TestMetricsEndpoint:
    """Test the /metrics Prometheus endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self):
        """Test that /metrics endpoint returns 200 without auth."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint_content_type(self):
        """Test that /metrics returns Prometheus content type."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics")
            content_type = response.headers.get("content-type", "")
            # Prometheus exposition format
            assert "text/plain" in content_type or "text" in content_type.lower()

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_novamind_metrics(self):
        """Test that /metrics includes our custom metrics."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app

        # Record some metrics first
        PrometheusMetrics.record_message_processed()
        PrometheusMetrics.record_llm_request("gemini", "test", "success")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics")
            body = response.text
            assert "novamind" in body


# ============= SYSTEM METRICS ENDPOINT TESTS =============

class TestSystemMetricsEndpoint:
    """Test the /api/system/metrics endpoint."""

    @pytest.mark.asyncio
    async def test_system_metrics_endpoint(self):
        """Test that /api/system/metrics returns comprehensive stats."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app

        # Mock get_db to return None (DB not available)
        async def mock_get_db():
            yield None

        app.dependency_overrides[get_db] = mock_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/system/metrics")
                # Should return 200 with DB stats marked as not available, or 401 if auth required
                assert response.status_code in (200, 401)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_system_metrics_with_auth_disabled(self):
        """Test system metrics when auth is disabled."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app
        import api.main as main_module
        from unittest.mock import AsyncMock, patch

        # Temporarily disable auth
        original = main_module.AUTH_REQUIRED
        main_module.AUTH_REQUIRED = False

        # Mock get_db to avoid DB initialization requirement
        async def mock_get_db():
            yield None

        try:
            # Override the get_db dependency
            app.dependency_overrides[get_db] = mock_get_db

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/system/metrics")
                assert response.status_code == 200
                data = response.json()
                
                # Verify structure
                assert "cost_tracking" in data
                assert "tool_audit" in data
                assert "rate_limiter" in data
                assert "database" in data
                assert "application" in data
                
                # Verify application info
                assert data["application"]["version"] == "3.2.0"
                assert "uptime_seconds" in data["application"]
        finally:
            main_module.AUTH_REQUIRED = original
            app.dependency_overrides.clear()


# ============= INTEGRATION TESTS =============

class TestMonitoringIntegration:
    """Integration tests for the monitoring system."""

    def test_full_logging_pipeline(self):
        """Test the complete logging pipeline from setup to log output."""
        # Setup
        setup_structured_logging(log_level="INFO", json_output=True)
        
        # Get logger
        logger = MonitoringLogger.get_logger("test.integration")
        
        # Bind context
        MonitoringLogger.bind_context(request_id="integration-test-001")
        
        # Log various events
        MonitoringLogger.log_http_request(
            method="POST",
            path="/api/chat",
            status_code=200,
            duration_ms=1500.0,
            request_id="integration-test-001",
            user_id="test-user",
        )
        
        MonitoringLogger.log_llm_call(
            provider="gemini",
            model="gemini-2.0-flash",
            duration_ms=1200.0,
            input_tokens=200,
            output_tokens=100,
            success=True,
        )
        
        MonitoringLogger.log_tool_execution(
            tool_name="web_search",
            duration_ms=300.0,
            success=True,
        )
        
        # Clear context
        MonitoringLogger.clear_context()

    def test_prometheus_metrics_flow(self):
        """Test the full Prometheus metrics collection flow."""
        # Record various metrics
        PrometheusMetrics.record_llm_request("gemini", "gemini-2.0-flash", "success")
        PrometheusMetrics.record_llm_duration("gemini", "gemini-2.0-flash", 1.5)
        PrometheusMetrics.record_llm_tokens("gemini", "input", 100)
        PrometheusMetrics.record_llm_tokens("gemini", "output", 50)
        PrometheusMetrics.record_tool_execution("web_search", "success")
        PrometheusMetrics.record_tool_duration("web_search", 0.3)
        PrometheusMetrics.record_conversation_created()
        PrometheusMetrics.record_message_processed()
        PrometheusMetrics.record_error("ValidationError", "input")
        PrometheusMetrics.set_circuit_breaker_state("gemini", "closed")
        PrometheusMetrics.set_active_users(10)
        PrometheusMetrics.set_system_info("3.2.0", "test")

        # Verify metrics are generated
        text = get_metrics_text()
        assert "novamind_llm_requests_total" in text
        assert "novamind_tool_executions_total" in text
        assert "novamind_conversations_total" in text
        assert "novamind_messages_total" in text

    def test_sentry_graceful_degradation(self):
        """Test that Sentry degrades gracefully without DSN."""
        # Ensure Sentry is disabled
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SENTRY_DSN", None)
            setup_sentry()
            
            # All operations should work without errors
            assert is_sentry_enabled() is False
            assert capture_error(Exception("test")) is None
            add_breadcrumb("test", "test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
