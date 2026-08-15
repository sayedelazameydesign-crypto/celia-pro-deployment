"""
celia.pro Agent Safety
=======================
Execution limits, circuit breaker, retry logic, and cost tracking.
"""

import time
import logging
from typing import Dict, Optional, Any, List
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============= STRUCTURED ERRORS =============

class CeliaError(Exception):
    """Base error for celia.pro with structured information."""
    def __init__(self, code: str, message: str, retryable: bool = False,
                 details: Optional[Dict] = None):
        self.code = code
        self.retryable = retryable
        self.details = details or {}
        super().__init__(message)


class ProviderError(CeliaError):
    """Error from an LLM provider."""
    pass


class ProviderTimeout(ProviderError):
    def __init__(self, provider: str, timeout: float):
        super().__init__(
            code="PROVIDER_TIMEOUT",
            message=f"Provider '{provider}' timed out after {timeout}s",
            retryable=True,
            details={"provider": provider, "timeout": timeout}
        )


class ProviderRateLimited(ProviderError):
    def __init__(self, provider: str, retry_after: int = 60):
        super().__init__(
            code="PROVIDER_RATE_LIMITED",
            message=f"Provider '{provider}' rate limited",
            retryable=True,
            details={"provider": provider, "retry_after": retry_after}
        )


class ProviderUnavailable(ProviderError):
    def __init__(self, provider: str, reason: str = ""):
        super().__init__(
            code="PROVIDER_UNAVAILABLE",
            message=f"Provider '{provider}' is unavailable: {reason}",
            retryable=True,
            details={"provider": provider, "reason": reason}
        )


class ToolExecutionError(CeliaError):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            code="TOOL_EXECUTION_ERROR",
            message=f"Tool '{tool_name}' failed: {reason}",
            retryable=False,
            details={"tool": tool_name}
        )


class AgentLimitExceeded(CeliaError):
    def __init__(self, limit_name: str, current: int, maximum: int):
        super().__init__(
            code="AGENT_LIMIT_EXCEEDED",
            message=f"Agent limit '{limit_name}' exceeded: {current}/{maximum}",
            retryable=False,
            details={"limit": limit_name, "current": current, "maximum": maximum}
        )


class SafetyViolation(CeliaError):
    def __init__(self, reason: str):
        super().__init__(
            code="SAFETY_VIOLATION",
            message=f"Safety check failed: {reason}",
            retryable=False,
        )


# ============= AGENT SAFETY LIMITS =============

@dataclass
class AgentLimits:
    """Safety limits for agent execution."""
    max_iterations: int = 20          # Maximum agent loop iterations
    max_tool_calls: int = 30          # Maximum total tool calls per task
    max_runtime_seconds: float = 120  # Maximum total runtime
    max_token_budget: int = 100_000   # Maximum tokens per conversation
    max_concurrent_tools: int = 3     # Maximum parallel tool executions
    max_message_history: int = 50     # Maximum messages in context


# Global default limits
DEFAULT_LIMITS = AgentLimits()


@dataclass
class AgentBudget:
    """Tracks resource usage during agent execution."""
    limits: AgentLimits
    iterations: int = 0
    tool_calls: int = 0
    tokens_used: int = 0
    start_time: float = field(default_factory=time.time)
    provider_costs: Dict[str, float] = field(default_factory=dict)

    def check_iteration(self):
        """Check if we can do another iteration."""
        self.iterations += 1
        if self.iterations > self.limits.max_iterations:
            raise AgentLimitExceeded(
                "max_iterations", self.iterations, self.limits.max_iterations
            )

    def check_tool_call(self):
        """Check if we can make another tool call."""
        self.tool_calls += 1
        if self.tool_calls > self.limits.max_tool_calls:
            raise AgentLimitExceeded(
                "max_tool_calls", self.tool_calls, self.limits.max_tool_calls
            )

    def check_runtime(self):
        """Check if we've exceeded the runtime limit."""
        elapsed = time.time() - self.start_time
        if elapsed > self.limits.max_runtime_seconds:
            raise AgentLimitExceeded(
                "max_runtime_seconds",
                int(elapsed),
                int(self.limits.max_runtime_seconds)
            )

    def add_tokens(self, count: int, provider: str = "unknown"):
        """Track token usage."""
        self.tokens_used += count
        if self.tokens_used > self.limits.max_token_budget:
            raise AgentLimitExceeded(
                "max_token_budget", self.tokens_used, self.limits.max_token_budget
            )

    def get_status(self) -> Dict:
        """Get current budget status."""
        elapsed = time.time() - self.start_time
        return {
            "iterations": f"{self.iterations}/{self.limits.max_iterations}",
            "tool_calls": f"{self.tool_calls}/{self.limits.max_tool_calls}",
            "tokens_used": f"{self.tokens_used}/{self.limits.max_token_budget}",
            "runtime_seconds": f"{elapsed:.1f}/{self.limits.max_runtime_seconds}",
            "healthy": (
                self.iterations <= self.limits.max_iterations and
                self.tool_calls <= self.limits.max_tool_calls and
                self.tokens_used <= self.limits.max_token_budget and
                elapsed <= self.limits.max_runtime_seconds
            )
        }


# ============= CIRCUIT BREAKER =============

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for LLM providers.
    
    CLOSED: requests pass through
    OPEN: requests are rejected immediately
    HALF_OPEN: one test request allowed through
    """
    name: str
    failure_threshold: int = 5        # Failures before opening
    recovery_timeout: float = 60.0    # Seconds to wait before trying again
    success_threshold: int = 2        # Successes in half_open to close

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    last_state_change: float = field(default_factory=time.time)

    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change = time.time()
                logger.info(f"Circuit breaker '{self.name}': OPEN → HALF_OPEN")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Record a successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.time()
                logger.info(f"Circuit breaker '{self.name}': HALF_OPEN → CLOSED")
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            logger.warning(f"Circuit breaker '{self.name}': HALF_OPEN → OPEN")
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                logger.warning(
                    f"Circuit breaker '{self.name}': CLOSED → OPEN "
                    f"(failures: {self.failure_count})"
                )

    def get_status(self) -> Dict:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
        }


# ============= COST TRACKER =============

@dataclass
class CostEntry:
    """Tracks cost for a single request."""
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0  # $0 for free tier
    request_duration_ms: float = 0


class CostTracker:
    """Tracks token usage and estimated costs."""

    # Cost per 1K tokens (approximate, free tier = 0)
    PRICING = {
        "gemini-2.0-flash": {"input": 0.0, "output": 0.0},  # Free tier
        "gemini-1.5-flash": {"input": 0.0, "output": 0.0},
        "default": {"input": 0.0, "output": 0.0},
    }

    def __init__(self):
        self.entries: List[CostEntry] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0

    def record(self, entry: CostEntry):
        """Record a request's cost."""
        self.entries.append(entry)
        self.total_input_tokens += entry.input_tokens
        self.total_output_tokens += entry.output_tokens
        self.total_cost += entry.estimated_cost
        self.request_count += 1

        # Keep last 1000 entries
        if len(self.entries) > 1000:
            self.entries = self.entries[-1000:]

    def get_summary(self) -> Dict:
        """Get cost summary."""
        return {
            "total_requests": self.request_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "recent_requests": [
                {
                    "provider": e.provider,
                    "model": e.model,
                    "tokens": e.input_tokens + e.output_tokens,
                    "duration_ms": e.request_duration_ms,
                }
                for e in self.entries[-5:]
            ]
        }


# ============= STRUCTURED LOGGING =============

class StructuredLogger:
    """JSON structured logging for observability."""

    @staticmethod
    def log_event(event: str, level: str = "INFO", **kwargs):
        """Log a structured event."""
        import json
        entry = {
            "timestamp": time.time(),
            "level": level,
            "event": event,
            **kwargs
        }
        # Remove sensitive data
        for key in ["api_key", "token", "password", "secret"]:
            if key in entry:
                entry[key] = "***REDACTED***"

        log_func = getattr(logger, level.lower(), logger.info)
        log_func(json.dumps(entry, default=str))
