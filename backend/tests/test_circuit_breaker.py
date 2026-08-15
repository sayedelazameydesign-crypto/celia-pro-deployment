"""
Circuit Breaker Integration Tests for LLMRouter
================================================
Tests that verify circuit breaker is properly integrated with LLMRouter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time


class TestLLMRouterCircuitBreaker:
    """Test circuit breaker integration in LLMRouter."""
    
    @pytest.fixture
    def mock_gemini_client(self):
        """Create a mock Gemini client."""
        client = MagicMock()
        client.chat = AsyncMock()
        client.chat_with_tools = AsyncMock()
        client.close = AsyncMock()
        client.model = "gemini-2.0-flash"
        return client
    
    @pytest.fixture
    def mock_groq_client(self):
        """Create a mock Groq client."""
        client = MagicMock()
        client.chat = AsyncMock()
        client.chat_with_tools = AsyncMock()
        client.close = AsyncMock()
        client.model = "openai/gpt-oss-20b"
        return client
    
    @pytest.fixture
    def router_with_breakers(self, mock_gemini_client, mock_groq_client):
        """Create LLMRouter with circuit breakers."""
        from core.llm_clients import LLMRouter
        
        router = LLMRouter(gemini_key="fake_key", groq_key="fake_key", primary="gemini")
        # Replace real clients with mocks
        router.gemini = mock_gemini_client
        router.groq = mock_groq_client
        return router
    
    @pytest.mark.asyncio
    async def test_router_has_circuit_breakers(self, router_with_breakers):
        """Test that router creates circuit breakers for each provider."""
        assert "gemini" in router_with_breakers.circuit_breakers
        assert "groq" in router_with_breakers.circuit_breakers
        assert router_with_breakers.circuit_breakers["gemini"].name == "gemini"
        assert router_with_breakers.circuit_breakers["groq"].name == "groq"
    
    @pytest.mark.asyncio
    async def test_successful_request_records_success(self, router_with_breakers, mock_gemini_client):
        """Test that successful request records success in circuit breaker."""
        mock_gemini_client.chat.return_value = {"content": "Hello", "role": "assistant"}
        
        result = await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        assert result["content"] == "Hello"
        # Circuit breaker should have recorded success
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        assert gemini_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_failed_request_records_failure(self, router_with_breakers, mock_gemini_client, mock_groq_client):
        """Test that failed request records failure and falls back."""
        # Gemini fails
        mock_gemini_client.chat.side_effect = Exception("Gemini error")
        # Groq succeeds
        mock_groq_client.chat.return_value = {"content": "Hello from Groq", "role": "assistant"}
        
        result = await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        assert result["content"] == "Hello from Groq"
        # Gemini circuit breaker should have recorded failure
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        assert gemini_breaker.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, router_with_breakers, mock_gemini_client, mock_groq_client):
        """Test that circuit opens after reaching failure threshold."""
        # Make Gemini always fail
        mock_gemini_client.chat.side_effect = Exception("Gemini error")
        mock_groq_client.chat.return_value = {"content": "Fallback", "role": "assistant"}
        
        # Set low threshold for testing
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        gemini_breaker.failure_threshold = 3
        
        # Trigger 3 failures
        for _ in range(3):
            await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        # Circuit should be OPEN
        assert gemini_breaker.state.value == "open"
        
        # Next request should skip Gemini entirely
        mock_gemini_client.chat.reset_mock()
        await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        # Gemini should not be called
        mock_gemini_client.chat.assert_not_called()
        # Groq should be called
        mock_groq_client.chat.assert_called()
    
    @pytest.mark.asyncio
    async def test_circuit_half_open_after_timeout(self, router_with_breakers, mock_gemini_client, mock_groq_client):
        """Test that circuit transitions to HALF_OPEN after recovery timeout."""
        from core.agent_safety import CircuitState
        
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        gemini_breaker.failure_threshold = 2
        gemini_breaker.recovery_timeout = 0.1  # 100ms for testing
        
        # Open the circuit
        gemini_breaker.record_failure()
        gemini_breaker.record_failure()
        assert gemini_breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Next request should transition to HALF_OPEN
        mock_gemini_client.chat.return_value = {"content": "Recovered", "role": "assistant"}
        result = await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        assert gemini_breaker.state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_in_half_open(self, router_with_breakers, mock_gemini_client):
        """Test that circuit closes after success in HALF_OPEN state."""
        from core.agent_safety import CircuitState
        
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        gemini_breaker.failure_threshold = 2
        gemini_breaker.recovery_timeout = 0.1
        gemini_breaker.success_threshold = 1
        
        # Open the circuit
        gemini_breaker.record_failure()
        gemini_breaker.record_failure()
        assert gemini_breaker.state == CircuitState.OPEN
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Successful request in HALF_OPEN
        mock_gemini_client.chat.return_value = {"content": "Success", "role": "assistant"}
        await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        # Circuit should be HALF_OPEN then CLOSED after success
        # (depends on success_threshold)
        assert gemini_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_reopens_on_failure_in_half_open(self, router_with_breakers, mock_gemini_client, mock_groq_client):
        """Test that circuit reopens on failure in HALF_OPEN state."""
        from core.agent_safety import CircuitState
        
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        gemini_breaker.failure_threshold = 2
        gemini_breaker.recovery_timeout = 0.1
        gemini_breaker.success_threshold = 2  # Need 2 successes to close
        
        # Open the circuit
        gemini_breaker.record_failure()
        gemini_breaker.record_failure()
        assert gemini_breaker.state == CircuitState.OPEN
        
        # Wait for recovery
        time.sleep(0.15)
        
        # Failed request in HALF_OPEN
        mock_gemini_client.chat.side_effect = Exception("Still failing")
        mock_groq_client.chat.return_value = {"content": "Fallback", "role": "assistant"}
        await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        # Circuit should be back to OPEN
        assert gemini_breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_chat_with_tools_uses_circuit_breaker(self, router_with_breakers, mock_gemini_client, mock_groq_client):
        """Test that chat_with_tools also uses circuit breaker."""
        mock_gemini_client.chat_with_tools.side_effect = Exception("Gemini error")
        mock_groq_client.chat_with_tools.return_value = {"content": "Tool result", "role": "assistant"}
        
        result = await router_with_breakers.chat_with_tools(
            messages=[{"role": "user", "content": "Use tool"}],
            tools=[{"type": "function", "function": {"name": "test"}}]
        )
        
        assert result["content"] == "Tool result"
        gemini_breaker = router_with_breakers.circuit_breakers["gemini"]
        assert gemini_breaker.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self, router_with_breakers, mock_gemini_client, mock_groq_client):
        """Test that exception is raised when all providers fail."""
        mock_gemini_client.chat.side_effect = Exception("Gemini error")
        mock_groq_client.chat.side_effect = Exception("Groq error")
        
        with pytest.raises(Exception) as exc_info:
            await router_with_breakers.chat([{"role": "user", "content": "Hi"}])
        
        assert "All LLM providers failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_status_includes_circuit_breakers(self, router_with_breakers):
        """Test that get_status includes circuit breaker information."""
        status = router_with_breakers.get_status()
        
        assert "circuit_breakers" in status
        assert "gemini" in status["circuit_breakers"]
        assert "groq" in status["circuit_breakers"]
        assert "state" in status["circuit_breakers"]["gemini"]
        assert status["circuit_breakers"]["gemini"]["state"] == "closed"


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""
    
    def test_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        from core.agent_safety import CircuitBreaker, CircuitState
        
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED
    
    def test_can_execute_when_closed(self):
        """Test that can_execute returns True when CLOSED."""
        from core.agent_safety import CircuitBreaker
        
        breaker = CircuitBreaker(name="test")
        assert breaker.can_execute() is True
    
    def test_cannot_execute_when_open(self):
        """Test that can_execute returns False when OPEN."""
        from core.agent_safety import CircuitBreaker, CircuitState
        import time
        
        breaker = CircuitBreaker(name="test", recovery_timeout=60.0)
        # Manually set to OPEN
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = time.time()
        
        assert breaker.can_execute() is False
    
    def test_can_execute_when_half_open(self):
        """Test that can_execute returns True when HALF_OPEN."""
        from core.agent_safety import CircuitBreaker, CircuitState
        
        breaker = CircuitBreaker(name="test")
        # Manually set to HALF_OPEN
        breaker.state = CircuitState.HALF_OPEN
        
        assert breaker.can_execute() is True
    
    def test_record_failure_increments_counter(self):
        """Test that record_failure increments failure count."""
        from core.agent_safety import CircuitBreaker
        
        breaker = CircuitBreaker(name="test")
        assert breaker.failure_count == 0
        
        breaker.record_failure()
        assert breaker.failure_count == 1
        
        breaker.record_failure()
        assert breaker.failure_count == 2
    
    def test_record_success_in_closed_resets_failure(self):
        """Test that record_success in CLOSED state resets failure count."""
        from core.agent_safety import CircuitBreaker
        
        breaker = CircuitBreaker(name="test")
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        
        breaker.record_success()
        assert breaker.failure_count == 1  # Decremented
    
    def test_get_status_returns_correct_info(self):
        """Test that get_status returns correct information."""
        from core.agent_safety import CircuitBreaker
        
        breaker = CircuitBreaker(name="test_provider")
        status = breaker.get_status()
        
        assert status["name"] == "test_provider"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
