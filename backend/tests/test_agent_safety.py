"""
celia.pro Agent Safety Tests
==============================
Tests for execution limits, circuit breaker, and cost tracking.
"""

import sys
import os
import time
import pytest


from core.agent_safety import (
    AgentLimits, AgentBudget, AgentLimitExceeded,
    CircuitBreaker, CircuitState,
    CostTracker, CostEntry,
    CeliaError, ProviderError, ProviderTimeout,
    ProviderRateLimited, ProviderUnavailable,
    ToolExecutionError, SafetyViolation,
)


# ============= AGENT BUDGET TESTS =============

class TestAgentBudget:
    """Test agent execution limits."""

    def test_iteration_limit(self):
        limits = AgentLimits(max_iterations=3)
        budget = AgentBudget(limits=limits)
        budget.check_iteration()
        budget.check_iteration()
        budget.check_iteration()
        with pytest.raises(AgentLimitExceeded, match="max_iterations"):
            budget.check_iteration()

    def test_tool_call_limit(self):
        limits = AgentLimits(max_tool_calls=2)
        budget = AgentBudget(limits=limits)
        budget.check_tool_call()
        budget.check_tool_call()
        with pytest.raises(AgentLimitExceeded, match="max_tool_calls"):
            budget.check_tool_call()

    def test_token_budget(self):
        limits = AgentLimits(max_token_budget=1000)
        budget = AgentBudget(limits=limits)
        budget.add_tokens(500)
        budget.add_tokens(400)
        with pytest.raises(AgentLimitExceeded, match="max_token_budget"):
            budget.add_tokens(200)

    def test_runtime_check(self):
        limits = AgentLimits(max_runtime_seconds=0.1)
        budget = AgentBudget(limits=limits)
        time.sleep(0.15)
        with pytest.raises(AgentLimitExceeded, match="max_runtime_seconds"):
            budget.check_runtime()

    def test_budget_status(self):
        limits = AgentLimits(max_iterations=5, max_tool_calls=10)
        budget = AgentBudget(limits=limits)
        budget.check_iteration()
        budget.check_tool_call()
        status = budget.get_status()
        assert status["healthy"] is True
        assert "1/5" in status["iterations"]
        assert "1/10" in status["tool_calls"]

    def test_budget_unhealthy_after_limit(self):
        limits = AgentLimits(max_iterations=1)
        budget = AgentBudget(limits=limits)
        budget.check_iteration()
        try:
            budget.check_iteration()
        except AgentLimitExceeded:
            pass
        status = budget.get_status()
        assert status["healthy"] is False


# ============= CIRCUIT BREAKER TESTS =============

class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_failures(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # Still closed
        cb.record_failure()  # Third failure
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.can_execute() is True  # Transitions to HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1, success_threshold=1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Triggers HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1, success_threshold=2)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Triggers HALF_OPEN
        cb.record_failure()  # Fail again
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # Decrements failure count
        assert cb.failure_count == 1

    def test_status(self):
        cb = CircuitBreaker(name="test")
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["state"] == "closed"


# ============= COST TRACKER TESTS =============

class TestCostTracker:
    """Test cost tracking."""

    def test_record_entry(self):
        tracker = CostTracker()
        entry = CostEntry(
            provider="gemini",
            model="gemini-2.0-flash",
            input_tokens=100,
            output_tokens=50,
        )
        tracker.record(entry)
        summary = tracker.get_summary()
        assert summary["total_requests"] == 1
        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50

    def test_accumulates_costs(self):
        tracker = CostTracker()
        for i in range(5):
            tracker.record(CostEntry(
                provider="gemini",
                model="gemini-2.0-flash",
                input_tokens=100,
                output_tokens=50,
            ))
        summary = tracker.get_summary()
        assert summary["total_requests"] == 5
        assert summary["total_tokens"] == 750

    def test_free_tier_zero_cost(self):
        tracker = CostTracker()
        tracker.record(CostEntry(
            provider="gemini",
            model="gemini-2.0-flash",
            input_tokens=1000000,
            output_tokens=500000,
            estimated_cost=0.0,  # Free tier
        ))
        assert tracker.total_cost == 0.0


# ============= STRUCTURED ERROR TESTS =============

class TestStructuredErrors:
    """Test structured error types."""

    def test_provider_timeout(self):
        error = ProviderTimeout("gemini", 30.0)
        assert error.code == "PROVIDER_TIMEOUT"
        assert error.retryable is True
        assert "gemini" in str(error)

    def test_provider_rate_limited(self):
        error = ProviderRateLimited("gemini", retry_after=60)
        assert error.code == "PROVIDER_RATE_LIMITED"
        assert error.retryable is True

    def test_provider_unavailable(self):
        error = ProviderUnavailable("huggingface", "model loading")
        assert error.code == "PROVIDER_UNAVAILABLE"
        assert error.retryable is True

    def test_tool_execution_error(self):
        error = ToolExecutionError("execute_code", "syntax error")
        assert error.code == "TOOL_EXECUTION_ERROR"
        assert error.retryable is False

    def test_safety_violation(self):
        error = SafetyViolation("sandbox escape attempt")
        assert error.code == "SAFETY_VIOLATION"
        assert error.retryable is False

    def test_agent_limit_exceeded(self):
        error = AgentLimitExceeded("max_iterations", 21, 20)
        assert error.code == "AGENT_LIMIT_EXCEEDED"
        assert "21/20" in str(error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
