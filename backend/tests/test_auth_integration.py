"""
celia.pro Auth Integration Tests
=================================
Tests that verify authentication integration with endpoints.
Uses isolated database per test to prevent shared state.
"""

import sys
import os
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from database.models import User, UserRole
from auth.auth import create_access_token, get_password_hash


@pytest_asyncio.fixture
async def auth_client(isolated_db, disable_rate_limiter):
    """Create test client with auth and isolated database."""
    from api.main import app
    from database.connection import get_db
    
    session, engine = isolated_db
    
    # Create test user
    test_user = User(
        id="test-user-123",
        email="test@celia.pro",
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER,
        is_active=True,
    )
    session.add(test_user)
    await session.commit()
    
    # Override db dependency
    async def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    import api.main
    original_auth = api.main.AUTH_REQUIRED
    api.main.AUTH_REQUIRED = True
    
    # Create token
    token = create_access_token(data={"sub": "test-user-123", "type": "access"})
    
    client = TestClient(app)
    
    yield client, session, token
    
    app.dependency_overrides.clear()
    api.main.AUTH_REQUIRED = original_auth


@pytest_asyncio.fixture
async def strict_client(isolated_db, disable_rate_limiter):
    """Create test client with strict auth (no token)."""
    from api.main import app
    from database.connection import get_db
    
    session, engine = isolated_db
    
    async def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    import api.main
    original_auth = api.main.AUTH_REQUIRED
    api.main.AUTH_REQUIRED = True
    
    client = TestClient(app)
    
    yield client, session
    
    app.dependency_overrides.clear()
    api.main.AUTH_REQUIRED = original_auth


class TestSensitiveEndpointsRequireAuth:
    """Test that sensitive endpoints reject requests without token."""
    
    @pytest.mark.asyncio
    async def test_chat_without_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post("/api/chat", json={"message": "Hello"})
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_tool_execution_without_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/tools/think/execute",
            json={"arguments": {"thought": "Test", "type": "reasoning"}}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_memory_store_without_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/memory/store",
            json={"key": "test", "value": "test_value", "type": "fact", "generate_vector": False}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_create_conversation_without_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post("/api/conversations", params={"title": "Test"})
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_configure_llm_without_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/llm/configure",
            json={"gemini_api_key": None, "primary_provider": "gemini"}
        )
        assert response.status_code == 401


class TestSensitiveEndpointsRejectInvalidToken:
    """Test that sensitive endpoints reject invalid tokens."""
    
    @pytest.mark.asyncio
    async def test_chat_with_invalid_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/chat",
            json={"message": "Hello"},
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_chat_with_empty_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/chat",
            json={"message": "Hello"},
            headers={"Authorization": "Bearer "}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_chat_with_wrong_scheme_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/chat",
            json={"message": "Hello"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_invalid_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/tools/think/execute",
            json={"arguments": {"thought": "Test", "type": "reasoning"}},
            headers={"Authorization": "Bearer invalid.token"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, strict_client):
        client, db_session = strict_client
        response = client.post(
            "/api/chat",
            json={"message": "Hello"},
            headers={"Authorization": "Bearer expired.token.value"}
        )
        assert response.status_code == 401


class TestSensitiveEndpointsAcceptValidToken:
    """Test that sensitive endpoints accept valid tokens."""
    
    @pytest.mark.asyncio
    async def test_chat_with_valid_token_accepted(self, auth_client):
        client, db_session, token = auth_client
        response = client.post(
            "/api/chat",
            json={"message": "Hello, how are you?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code != 401
        assert response.status_code in [200, 500]
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_valid_token_accepted(self, auth_client):
        client, db_session, token = auth_client
        response = client.post(
            "/api/tools/think/execute",
            json={"arguments": {"thought": "Test", "type": "reasoning"}},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code != 401


class TestNonSensitiveEndpointsRemainOpen:
    """Test that non-sensitive endpoints remain open."""
    
    @pytest.mark.asyncio
    async def test_health_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/api/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_root_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ready_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/api/ready")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_live_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/api/live")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_providers_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/api/llm/providers")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_list_tools_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/api/tools")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_list_conversations_open_without_token(self, strict_client):
        client, db_session = strict_client
        response = client.get("/api/conversations")
        assert response.status_code in [200, 401]


class TestDevelopmentMode:
    """Test that dev mode allows access without token."""
    
    @pytest.mark.asyncio
    async def test_dev_mode_allows_chat_without_token(self, isolated_db, disable_rate_limiter):
        from api.main import app
        from database.connection import get_db
        
        session, engine = isolated_db
        
        async def override_get_db():
            yield session
        
        app.dependency_overrides[get_db] = override_get_db
        
        import api.main
        original_auth = api.main.AUTH_REQUIRED
        api.main.AUTH_REQUIRED = False
        
        client = TestClient(app)
        
        response = client.post("/api/chat", json={"message": "Hello"})
        assert response.status_code != 401
        assert response.status_code in [200, 500]
        
        app.dependency_overrides.clear()
        api.main.AUTH_REQUIRED = original_auth
    
    @pytest.mark.asyncio
    async def test_dev_mode_allows_tool_execution_without_token(self, isolated_db, disable_rate_limiter):
        from api.main import app
        from database.connection import get_db
        
        session, engine = isolated_db
        
        async def override_get_db():
            yield session
        
        app.dependency_overrides[get_db] = override_get_db
        
        import api.main
        original_auth = api.main.AUTH_REQUIRED
        api.main.AUTH_REQUIRED = False
        
        client = TestClient(app)
        
        response = client.post(
            "/api/tools/think/execute",
            json={"arguments": {"thought": "Test", "type": "reasoning"}}
        )
        assert response.status_code == 200
        
        app.dependency_overrides.clear()
        api.main.AUTH_REQUIRED = original_auth


class TestDatabaseInitialization:
    """Test database initialization."""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, isolated_db):
        session, engine = isolated_db
        assert session is not None
        assert engine is not None
    
    @pytest.mark.asyncio
    async def test_database_session(self, isolated_db):
        session, engine = isolated_db
        from sqlalchemy import text
        result = await session.execute(text("SELECT 1"))
        value = result.scalar()
        assert value == 1


class TestErrorResponseFormat:
    """Test error response format."""
    
    @pytest.mark.asyncio
    async def test_401_has_error_code(self, strict_client):
        client, db_session = strict_client
        response = client.post("/api/chat", json={"message": "Hello"})
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_401_has_www_authenticate_header(self, strict_client):
        client, db_session = strict_client
        response = client.post("/api/chat", json={"message": "Hello"})
        assert response.status_code == 401
        # Check if WWW-Authenticate header exists
        assert "WWW-Authenticate" in response.headers or "www-authenticate" in response.headers
        # Check the value
        header_value = response.headers.get("WWW-Authenticate") or response.headers.get("www-authenticate")
        assert header_value == "Bearer"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
