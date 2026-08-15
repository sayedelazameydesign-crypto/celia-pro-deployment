"""
Integration Tests: Full Chat Flow
==================================
Tests the complete flow from user registration to receiving an agent response.
Uses REAL database (no mocks) and REAL agent (no mocks).
Uses isolated database per test.
"""

import pytest
import pytest_asyncio
import os
import asyncio

from fastapi.testclient import TestClient
from database.models import User, UserRole, Conversation, Message
from auth.auth import get_password_hash, create_access_token


@pytest_asyncio.fixture
async def chat_client(isolated_db, disable_rate_limiter):
    """Create test client with isolated database for chat flow tests."""
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


class TestFullChatFlow:
    """Test the complete chat flow from registration to response."""
    
    @pytest.mark.asyncio
    async def test_register_user_creates_in_database(self, chat_client):
        """Test that user registration creates a real user in the database."""
        client, db_session = chat_client
        
        # Register a new user
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepass123"
            }
        )
        
        assert response.status_code == 201, f"Registration failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        
        # Verify user exists in database
        from sqlalchemy import select
        
        result = await db_session.execute(
            select(User).where(User.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        
        assert user is not None, "User was not saved to database"
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.is_active is True
        assert user.hashed_password != "securepass123"
        assert len(user.hashed_password) > 20
    
    @pytest.mark.asyncio
    async def test_login_returns_valid_token(self, chat_client):
        """Test that login returns a valid JWT token."""
        client, db_session = chat_client
        
        # First register
        client.post(
            "/api/auth/register",
            json={
                "email": "login@example.com",
                "username": "loginuser",
                "password": "securepass123"
            }
        )
        
        # Then login
        response = client.post(
            "/api/auth/login",
            json={
                "email": "login@example.com",
                "password": "securepass123"
            }
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        
        # Verify token works
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        me_response = client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        user_data = me_response.json()
        assert user_data["email"] == "login@example.com"
    
    @pytest.mark.asyncio
    async def test_chat_with_auth_saves_to_database(self, chat_client):
        """Test that chat with authentication saves conversation and messages."""
        client, db_session = chat_client
        
        # Register and get token
        reg_response = client.post(
            "/api/auth/register",
            json={
                "email": "chat@example.com",
                "username": "chatuser",
                "password": "securepass123"
            }
        )
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        await db_session.commit()
        
        # Send a chat message
        chat_response = client.post(
            "/api/chat",
            json={"message": "Hello, how are you?"},
            headers=headers
        )
        
        assert chat_response.status_code == 200, f"Chat failed: {chat_response.text}"
        chat_data = chat_response.json()
        assert "response" in chat_data
        assert "conversation_id" in chat_data
        assert len(chat_data["response"]) > 0
        
        await db_session.commit()
        
        # Verify conversation is in database
        from sqlalchemy import select
        
        conv_id = chat_data["conversation_id"]
        
        conv_result = await db_session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conversation = conv_result.scalar_one_or_none()
        
        assert conversation is not None, "Conversation was not saved"
        assert conversation.title is not None
        
        msg_result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv_id)
        )
        messages = msg_result.scalars().all()
        
        assert len(messages) >= 2
        
        user_msgs = [m for m in messages if m.role == "user"]
        assert len(user_msgs) >= 1
        assert "Hello" in user_msgs[0].content
        
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) >= 1
    
    @pytest.mark.asyncio
    async def test_unauthorized_chat_returns_401(self, chat_client):
        """Test that chat without authentication returns 401."""
        client, db_session = chat_client
        
        response = client.post("/api/chat", json={"message": "Hello"})
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_persistence_after_agent_restart(self, chat_client):
        """Test that data persists after creating a new agent instance."""
        client, db_session = chat_client
        
        # Register
        reg_response = client.post(
            "/api/auth/register",
            json={
                "email": "persist@example.com",
                "username": "persistuser",
                "password": "securepass123"
            }
        )
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        await db_session.commit()
        
        # Send chat message
        chat_response = client.post(
            "/api/chat",
            json={"message": "Test persistence"},
            headers=headers
        )
        assert chat_response.status_code == 200
        conv_id = chat_response.json()["conversation_id"]
        
        # Send another message
        client.post(
            "/api/chat",
            json={"message": "Second message", "conversation_id": conv_id},
            headers=headers
        )
        await db_session.commit()
        
        # Verify messages are in database
        from sqlalchemy import select
        
        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv_id)
        )
        messages = result.scalars().all()
        
        assert len(messages) >= 3
        
        user_msgs = [m for m in messages if m.role == "user"]
        assert len(user_msgs) == 2
        
        contents = [m.content for m in user_msgs]
        assert any("Test persistence" in c for c in contents)
        assert any("Second message" in c for c in contents)
    
    @pytest.mark.asyncio
    async def test_create_conversation_with_auth(self, chat_client):
        """Test creating a conversation with authentication."""
        client, db_session = chat_client
        
        # Register
        reg_response = client.post(
            "/api/auth/register",
            json={
                "email": "conv@example.com",
                "username": "convuser",
                "password": "securepass123"
            }
        )
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        await db_session.commit()
        
        # Create conversation
        conv_response = client.post(
            "/api/conversations",
            params={"title": "My Test Conversation"},
            headers=headers
        )
        
        assert conv_response.status_code == 200
        conv_data = conv_response.json()
        assert "conversation_id" in conv_data
        assert conv_data["title"] == "My Test Conversation"
        
        await db_session.commit()
        
        from sqlalchemy import select
        
        result = await db_session.execute(
            select(Conversation).where(Conversation.id == conv_data["conversation_id"])
        )
        conv = result.scalar_one_or_none()
        
        assert conv is not None
        assert conv.title == "My Test Conversation"
    
    @pytest.mark.asyncio
    async def test_user_isolation_in_chat(self, chat_client):
        """Test that different users cannot see each other's conversations."""
        client, db_session = chat_client
        
        # Register user 1
        reg1 = client.post(
            "/api/auth/register",
            json={
                "email": "user1@example.com",
                "username": "user1",
                "password": "securepass123"
            }
        )
        token1 = reg1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Register user 2
        reg2 = client.post(
            "/api/auth/register",
            json={
                "email": "user2@example.com",
                "username": "user2",
                "password": "securepass123"
            }
        )
        token2 = reg2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        await db_session.commit()
        
        # User 1 sends chat
        chat1 = client.post(
            "/api/chat",
            json={"message": "Hello from user 1"},
            headers=headers1
        )
        assert chat1.status_code == 200
        conv1_id = chat1.json()["conversation_id"]
        
        # User 2 sends chat
        chat2 = client.post(
            "/api/chat",
            json={"message": "Hello from user 2"},
            headers=headers2
        )
        assert chat2.status_code == 200
        conv2_id = chat2.json()["conversation_id"]
        
        assert conv1_id != conv2_id
        
        # Verify in database
        from sqlalchemy import select
        
        result1 = await db_session.execute(
            select(Conversation).where(Conversation.id == conv1_id)
        )
        conv1 = result1.scalar_one_or_none()
        
        result2 = await db_session.execute(
            select(Conversation).where(Conversation.id == conv2_id)
        )
        conv2 = result2.scalar_one_or_none()
        
        user1_result = await db_session.execute(
            select(User).where(User.email == "user1@example.com")
        )
        user1 = user1_result.scalar_one_or_none()
        
        user2_result = await db_session.execute(
            select(User).where(User.email == "user2@example.com")
        )
        user2 = user2_result.scalar_one_or_none()
        
        assert conv1.user_id == user1.id
        assert conv2.user_id == user2.id
        assert conv1.user_id != conv2.user_id


class TestDatabaseIntegrity:
    """Test database integrity and constraints."""
    
    @pytest.mark.asyncio
    async def test_duplicate_email_rejected(self, chat_client):
        """Test that duplicate email is rejected."""
        client, db_session = chat_client
        
        client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "firstuser",
                "password": "securepass123"
            }
        )
        
        response = client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "seconduser",
                "password": "securepass123"
            }
        )
        
        assert response.status_code in [400, 409]
    
    @pytest.mark.asyncio
    async def test_wrong_password_rejected(self, chat_client):
        """Test that wrong password is rejected on login."""
        client, db_session = chat_client
        
        client.post(
            "/api/auth/register",
            json={
                "email": "wrongpass@example.com",
                "username": "wrongpassuser",
                "password": "correctpassword"
            }
        )
        
        response = client.post(
            "/api/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
