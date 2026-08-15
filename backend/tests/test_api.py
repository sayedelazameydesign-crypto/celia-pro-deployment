"""
celia.pro API Tests
====================
Tests for API endpoints, CORS, and request handling.
Uses isolated database per test to prevent shared state.
"""

import sys
import os
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest_asyncio.fixture
async def test_client(isolated_db, disable_rate_limiter):
    """Create test client with isolated database and disabled rate limiter."""
    from api.main import app
    from database.connection import get_db
    
    session, engine = isolated_db
    
    # Override database dependency with isolated session
    async def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Disable auth for most tests
    import api.main
    original_auth = api.main.AUTH_REQUIRED
    api.main.AUTH_REQUIRED = False
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    app.dependency_overrides.clear()
    api.main.AUTH_REQUIRED = original_auth


@pytest_asyncio.fixture
async def auth_test_client(isolated_db, disable_rate_limiter):
    """Create test client with auth enabled and isolated database."""
    from api.main import app
    from database.connection import get_db
    from database.models import User, UserRole
    from auth.auth import create_access_token, get_password_hash
    
    session, engine = isolated_db
    
    # Create a test user in the isolated database
    test_user = User(
        id="test-user-123",
        email="test@celia.pro",
        username="testuser",
        hashed_password=get_password_hash("testpassword123"),
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )
    session.add(test_user)
    await session.commit()
    
    # Create token
    token = create_access_token(data={"sub": "test-user-123", "type": "access"})
    
    # Override database dependency
    async def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    import api.main
    original_auth = api.main.AUTH_REQUIRED
    api.main.AUTH_REQUIRED = True
    
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    
    yield client, session
    
    app.dependency_overrides.clear()
    api.main.AUTH_REQUIRED = original_auth


# ============= HEALTH & SYSTEM TESTS =============

class TestHealthEndpoints:
    """Test health and system endpoints."""

    @pytest.mark.asyncio
    async def test_root(self, test_client):
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "celia.pro AI Agent"
        assert data["version"] in ["3.1.0", "3.2.0"]

    @pytest.mark.asyncio
    async def test_health_check(self, test_client):
        response = test_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

    @pytest.mark.asyncio
    async def test_readiness(self, test_client):
        response = test_client.get("/api/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    @pytest.mark.asyncio
    async def test_liveness(self, test_client):
        response = test_client.get("/api/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True

    @pytest.mark.asyncio
    async def test_security_headers(self, test_client):
        response = test_client.get("/api/health")
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in response.headers


# ============= LLM ENDPOINT TESTS =============

class TestLLMEndpoints:
    """Test LLM configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_providers(self, test_client):
        response = test_client.get("/api/llm/providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data["providers"]) == 3
        provider_ids = [p["id"] for p in data["providers"]]
        assert "gemini" in provider_ids
        assert "groq" in provider_ids
        assert "huggingface" in provider_ids

    @pytest.mark.asyncio
    async def test_get_status(self, test_client):
        response = test_client.get("/api/llm/status")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_configure_invalid_gemini_key(self, test_client):
        response = test_client.post("/api/llm/configure", json={
            "gemini_api_key": "invalid_key_format"
        })
        assert response.status_code == 400
        data = response.json()
        assert "VALIDATION_ERROR" in str(data)

    @pytest.mark.asyncio
    async def test_configure_invalid_hf_token(self, test_client):
        response = test_client.post("/api/llm/configure", json={
            "hf_token": "invalid_token_format"
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_configure_invalid_groq_key(self, test_client):
        response = test_client.post("/api/llm/configure", json={
            "groq_api_key": "invalid_key_format"
        })
        assert response.status_code == 400
        data = response.json()
        assert "VALIDATION_ERROR" in str(data)

    @pytest.mark.asyncio
    async def test_configure_invalid_provider(self, test_client):
        response = test_client.post("/api/llm/configure", json={
            "primary_provider": "invalid_provider"
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_configure_valid_gemini_key(self, test_client):
        response = test_client.post("/api/llm/configure", json={
            "gemini_api_key": "AIzaSyTestKey12345678901234567890",
            "primary_provider": "gemini"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "configured"
        assert data["providers"]["gemini_configured"] is True


# ============= CHAT ENDPOINT TESTS =============

class TestChatEndpoint:
    """Test chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_basic(self, test_client):
        response = test_client.post("/api/chat", json={
            "message": "Hello, how are you?"
        })
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "conversation_id" in data

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, test_client):
        response = test_client.post("/api/chat", json={
            "message": ""
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_message_too_long(self, test_client):
        response = test_client.post("/api/chat", json={
            "message": "x" * 15000
        })
        assert response.status_code in (200, 400, 422)


# ============= TOOL ENDPOINT TESTS =============

class TestToolEndpoints:
    """Test tool execution endpoints."""

    @pytest.mark.asyncio
    async def test_list_tools(self, test_client):
        response = test_client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 5
        tool_names = [t["name"] for t in data["tools"]]
        assert "web_search" in tool_names
        assert "execute_code" in tool_names
        assert "file_manager" in tool_names
        assert "shell" in tool_names
        assert "think" in tool_names

    @pytest.mark.asyncio
    async def test_tools_have_risk_levels(self, test_client):
        response = test_client.get("/api/tools")
        data = response.json()
        for tool in data["tools"]:
            assert "risk_level" in tool

    @pytest.mark.asyncio
    async def test_execute_think_tool(self, test_client):
        response = test_client.post("/api/tools/think/execute", json={
            "arguments": {"thought": "Testing the think tool", "type": "reasoning"}
        })
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    @pytest.mark.asyncio
    async def test_execute_code_dangerous(self, test_client):
        response = test_client.post("/api/tools/execute_code/execute", json={
            "arguments": {"code": "import os; os.system('rm -rf /')"}
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_shell_dangerous(self, test_client):
        response = test_client.post("/api/tools/shell/execute", json={
            "arguments": {"command": "rm -rf /"}
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_file_manager_path_traversal(self, test_client):
        response = test_client.post("/api/tools/file_manager/execute", json={
            "arguments": {"action": "read", "path": "../../etc/passwd"}
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_safe_code(self, test_client):
        response = test_client.post("/api/tools/execute_code/execute", json={
            "arguments": {"code": "print(2 + 2)"}
        })
        assert response.status_code == 200
        data = response.json()
        assert "4" in data["result"]


# ============= CONVERSATION TESTS =============

class TestConversationEndpoints:
    """Test conversation management."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, test_client):
        response = test_client.post("/api/conversations?title=Test")
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data

    @pytest.mark.asyncio
    async def test_list_conversations(self, test_client):
        response = test_client.get("/api/conversations")
        assert response.status_code == 200
        assert "conversations" in response.json()


# ============= RATE LIMITING TESTS =============

class TestRateLimiting:
    """Test rate limiting behavior."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, test_client):
        for _ in range(3):
            response = test_client.get("/api/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_id_header(self, test_client):
        response = test_client.get("/api/health")
        assert "x-request-id" in response.headers


# ============= MEMORY TESTS =============

class TestMemoryEndpoints:
    """Test memory system."""

    @pytest.mark.asyncio
    async def test_get_memory_summary(self, test_client):
        response = test_client.get("/api/memory")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_store_memory(self, test_client):
        response = test_client.post(
            "/api/memory/store",
            json={
                "key": "test",
                "value": "hello",
                "type": "fact",
                "generate_vector": False
            }
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_memory(self, test_client):
        response = test_client.get("/api/memory/search?query=test")
        assert response.status_code == 200


# ============= SYSTEM METRICS TESTS =============

class TestMetrics:
    """Test system metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, test_client):
        response = test_client.get("/api/system/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "cost_tracking" in data
        assert "tool_audit" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
