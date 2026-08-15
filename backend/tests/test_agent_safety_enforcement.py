"""
Agent Safety Enforcement Tests
================================
Tests that verify agent safety limits are enforced.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time


class TestAgentSafetyLimits:
    """Test agent safety limit enforcement."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client that returns tool calls."""
        client = MagicMock()
        client.chat_with_tools = AsyncMock()
        return client
    
    @pytest.fixture
    def agent_with_limits(self, mock_llm_client):
        """Create CeliaAgent with mock LLM client."""
        from core.agent import CeliaAgent
        
        agent = CeliaAgent()
        agent._llm_client = mock_llm_client
        return agent
    
    @pytest.mark.asyncio
    async def test_iteration_limit_enforced(self, agent_with_limits, mock_llm_client):
        """Test that agent stops when max_iterations is exceeded."""
        from core.agent_safety import AgentLimitExceeded
        
        # Make LLM always return tool calls (infinite loop scenario)
        mock_llm_client.chat_with_tools.return_value = {
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "think",
                    "arguments": '{"thought": "test"}'
                }
            }]
        }
        
        # Set low iteration limit for testing
        agent_with_limits.config.max_steps = 5
        
        # Mock tool execution
        with patch.object(agent_with_limits.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = "Tool result"
            
            # Mock budget with low limit
            from core.agent_safety import AgentBudget, AgentLimits
            budget = AgentBudget(limits=AgentLimits(max_iterations=3))
            
            # Should raise AgentLimitExceeded
            with pytest.raises(AgentLimitExceeded) as exc_info:
                await agent_with_limits._llm_agent_loop("test", [], budget)
            
            assert "max_iterations" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_tool_call_limit_enforced(self, agent_with_limits, mock_llm_client):
        """Test that agent stops when max_tool_calls is exceeded."""
        from core.agent_safety import AgentLimitExceeded
        
        # Make LLM return multiple tool calls
        mock_llm_client.chat_with_tools.return_value = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "think",
                        "arguments": '{"thought": "test 1"}'
                    }
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "think",
                        "arguments": '{"thought": "test 2"}'
                    }
                }
            ]
        }
        
        # Mock tool execution
        with patch.object(agent_with_limits.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = "Tool result"
            
            # Mock budget with low tool call limit
            from core.agent_safety import AgentBudget, AgentLimits
            budget = AgentBudget(limits=AgentLimits(max_tool_calls=3))
            
            # Should raise AgentLimitExceeded after 3 tool calls
            with pytest.raises(AgentLimitExceeded) as exc_info:
                await agent_with_limits._llm_agent_loop("test", [], budget)
            
            assert "max_tool_calls" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_runtime_limit_enforced(self, agent_with_limits, mock_llm_client):
        """Test that agent stops when max_runtime is exceeded."""
        from core.agent_safety import AgentLimitExceeded
        
        # Make LLM always return tool calls
        mock_llm_client.chat_with_tools.return_value = {
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "think",
                    "arguments": '{"thought": "test"}'
                }
            }]
        }
        
        # Mock tool execution with delay
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(0.2)
            return "Tool result"
        
        with patch.object(agent_with_limits.tool_registry, 'execute', side_effect=slow_execute):
            # Mock budget with very low runtime limit
            from core.agent_safety import AgentBudget, AgentLimits
            budget = AgentBudget(limits=AgentLimits(max_runtime_seconds=0.1))
            
            # Should raise AgentLimitExceeded
            with pytest.raises(AgentLimitExceeded) as exc_info:
                await agent_with_limits._llm_agent_loop("test", [], budget)
            
            assert "max_runtime_seconds" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_token_limit_enforced(self, agent_with_limits, mock_llm_client):
        """Test that agent stops when max_tokens is exceeded."""
        from core.agent_safety import AgentLimitExceeded
        
        # Mock budget with low token limit
        from core.agent_safety import AgentBudget, AgentLimits
        budget = AgentBudget(limits=AgentLimits(max_token_budget=100))
        
        # Add tokens to exceed limit - should raise immediately
        budget.add_tokens(50)
        
        with pytest.raises(AgentLimitExceeded) as exc_info:
            budget.add_tokens(60)  # This should raise
        
        assert "max_token_budget" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_budget_status_tracking(self, agent_with_limits, mock_llm_client):
        """Test that budget status is correctly tracked."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(
            max_iterations=10,
            max_tool_calls=20,
            max_runtime_seconds=60,
            max_token_budget=10000
        ))
        
        # Simulate some usage
        budget.check_iteration()
        budget.check_iteration()
        budget.check_tool_call()
        budget.add_tokens(500)
        
        status = budget.get_status()
        
        assert "2/10" in status["iterations"]
        assert "1/20" in status["tool_calls"]
        assert "500/10000" in status["tokens_used"]
        assert status["healthy"] is True
    
    @pytest.mark.asyncio
    async def test_process_message_handles_limit_exceeded(self, agent_with_limits, mock_llm_client):
        """Test that process_message gracefully handles AgentLimitExceeded."""
        from core.agent_safety import AgentLimitExceeded
        
        # Make LLM always return tool calls
        mock_llm_client.chat_with_tools.return_value = {
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "think",
                    "arguments": '{"thought": "test"}'
                }
            }]
        }
        
        # Mock tool execution
        with patch.object(agent_with_limits.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = "Tool result"
            
            # Mock _llm_agent_loop to raise AgentLimitExceeded
            with patch.object(agent_with_limits, '_llm_agent_loop', side_effect=AgentLimitExceeded("max_iterations", 21, 20)):
                # process_message should handle it gracefully
                response = await agent_with_limits.process_message("test")
                
                # Should return error message, not raise
                assert response is not None
                assert "safety limit" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_budget_healthy_when_within_limits(self, agent_with_limits, mock_llm_client):
        """Test that budget is healthy when within all limits."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(
            max_iterations=10,
            max_tool_calls=20,
            max_runtime_seconds=60,
            max_token_budget=10000
        ))
        
        # Use within limits
        for _ in range(5):
            budget.check_iteration()
        
        for _ in range(10):
            budget.check_tool_call()
        
        budget.add_tokens(5000)
        
        status = budget.get_status()
        assert status["healthy"] is True
    
    @pytest.mark.asyncio
    async def test_budget_unhealthy_when_exceeding_limits(self, agent_with_limits, mock_llm_client):
        """Test that budget is unhealthy when exceeding limits."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(
            max_iterations=10,
            max_tool_calls=20,
            max_runtime_seconds=60,
            max_token_budget=10000
        ))
        
        # Exceed iteration limit
        for _ in range(11):
            try:
                budget.check_iteration()
            except:
                pass
        
        status = budget.get_status()
        assert status["healthy"] is False


class TestAgentBudget:
    """Test AgentBudget class directly."""
    
    def test_initial_state(self):
        """Test that budget starts at zero."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits())
        
        assert budget.iterations == 0
        assert budget.tool_calls == 0
        assert budget.tokens_used == 0
    
    def test_check_iteration_increments(self):
        """Test that check_iteration increments counter."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(max_iterations=5))
        
        budget.check_iteration()
        assert budget.iterations == 1
        
        budget.check_iteration()
        assert budget.iterations == 2
    
    def test_check_iteration_raises_when_exceeded(self):
        """Test that check_iteration raises when limit exceeded."""
        from core.agent_safety import AgentBudget, AgentLimits, AgentLimitExceeded
        
        budget = AgentBudget(limits=AgentLimits(max_iterations=2))
        
        budget.check_iteration()  # 1
        budget.check_iteration()  # 2
        
        with pytest.raises(AgentLimitExceeded):
            budget.check_iteration()  # 3 - exceeds limit
    
    def test_check_tool_call_increments(self):
        """Test that check_tool_call increments counter."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(max_tool_calls=5))
        
        budget.check_tool_call()
        assert budget.tool_calls == 1
        
        budget.check_tool_call()
        assert budget.tool_calls == 2
    
    def test_check_tool_call_raises_when_exceeded(self):
        """Test that check_tool_call raises when limit exceeded."""
        from core.agent_safety import AgentBudget, AgentLimits, AgentLimitExceeded
        
        budget = AgentBudget(limits=AgentLimits(max_tool_calls=2))
        
        budget.check_tool_call()  # 1
        budget.check_tool_call()  # 2
        
        with pytest.raises(AgentLimitExceeded):
            budget.check_tool_call()  # 3 - exceeds limit
    
    def test_add_tokens_increments(self):
        """Test that add_tokens increments counter."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(max_token_budget=1000))
        
        budget.add_tokens(100)
        assert budget.tokens_used == 100
        
        budget.add_tokens(200)
        assert budget.tokens_used == 300
    
    def test_add_tokens_raises_when_exceeded(self):
        """Test that add_tokens raises when limit exceeded."""
        from core.agent_safety import AgentBudget, AgentLimits, AgentLimitExceeded
        
        budget = AgentBudget(limits=AgentLimits(max_token_budget=100))
        
        budget.add_tokens(50)
        
        with pytest.raises(AgentLimitExceeded):
            budget.add_tokens(60)  # This should raise
    
    def test_check_runtime_passes_when_within_limit(self):
        """Test that check_runtime passes when within limit."""
        from core.agent_safety import AgentBudget, AgentLimits
        
        budget = AgentBudget(limits=AgentLimits(max_runtime_seconds=60))
        
        # Should not raise
        budget.check_runtime()
    
    def test_check_runtime_raises_when_exceeded(self):
        """Test that check_runtime raises when limit exceeded."""
        from core.agent_safety import AgentBudget, AgentLimits, AgentLimitExceeded
        
        budget = AgentBudget(limits=AgentLimits(max_runtime_seconds=0.01))
        
        # Wait for runtime to exceed
        time.sleep(0.02)
        
        with pytest.raises(AgentLimitExceeded):
            budget.check_runtime()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
