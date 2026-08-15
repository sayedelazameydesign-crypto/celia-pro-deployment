"""
Integration Tests for Database Persistence
============================================
Tests that verify data persists across agent restarts.
Uses real SQLite database (no mocks).
"""

import pytest
import pytest_asyncio
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database.models import Base, Conversation, Message


@pytest_asyncio.fixture
async def test_db():
    """Create a fresh test database for each test."""
    db_url = "sqlite+aiosqlite:///./test_persistence.db"
    
    # Remove old test db if exists
    if os.path.exists("./test_persistence.db"):
        os.remove("./test_persistence.db")
    
    engine = create_async_engine(db_url, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with session_factory() as session:
        yield session
    
    # Cleanup
    await engine.dispose()
    if os.path.exists("./test_persistence.db"):
        os.remove("./test_persistence.db")


class TestDatabasePersistence:
    """Tests that verify data persistence across agent restarts."""
    
    @pytest.mark.asyncio
    async def test_conversation_persists_after_agent_restart(self, test_db):
        """
        Test that a conversation survives agent restart.
        This simulates the server being restarted.
        """
        from core.agent import CeliaAgent
        
        # Phase 1: Create agent and conversation
        agent1 = CeliaAgent(db=test_db, user_id="test-user-123")
        conv_id = await agent1.create_conversation("Test Conversation")
        
        # Verify conversation was created
        assert conv_id is not None
        assert len(conv_id) > 0
        
        # Commit to database
        await test_db.commit()
        
        # Phase 2: Simulate agent restart - create new agent with SAME db session
        # but new CeliaAgent instance
        agent2 = CeliaAgent(db=test_db, user_id="test-user-123")
        
        # Phase 3: Verify conversation still exists in database
        conversations = await agent2.list_conversations()
        assert len(conversations) >= 1
        
        # Find our conversation
        found = False
        for conv in conversations:
            if conv["id"] == conv_id:
                found = True
                assert conv["title"] == "Test Conversation"
                break
        
        assert found, "Conversation not found after agent restart"
    
    @pytest.mark.asyncio
    async def test_messages_persist_in_database(self, test_db):
        """Test that messages are saved to database and can be retrieved."""
        from core.agent import CeliaAgent
        
        # Create agent and conversation
        agent = CeliaAgent(db=test_db, user_id="test-user-123")
        conv_id = await agent.create_conversation("Message Test")
        
        # Process a message (this should save user + assistant messages to DB)
        response = await agent.process_message("Hello, how are you?", conv_id)
        
        # Commit to database
        await test_db.commit()
        
        # Verify response was generated
        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0
        
        # Retrieve history from database
        history = await agent.get_conversation_history(conv_id)
        
        # Should have at least system message + user message + assistant message
        assert len(history) >= 2
        
        # Find user message
        user_msgs = [m for m in history if m["role"] == "user"]
        assert len(user_msgs) >= 1
        assert "Hello" in user_msgs[0]["content"]
        
        # Find assistant message
        assistant_msgs = [m for m in history if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1
    
    @pytest.mark.asyncio
    async def test_data_survives_fresh_db_session(self, test_db):
        """
        Test that data persists even when creating a completely fresh session.
        This simulates closing the app and reopening it.
        """
        from core.agent import CeliaAgent
        from database.models import Conversation as DBConversation
        from sqlalchemy import select
        
        # Phase 1: Create data with first agent
        agent1 = CeliaAgent(db=test_db, user_id="test-user-persist")
        conv_id = await agent1.create_conversation("Persistence Test")
        await agent1.process_message("Test message", conv_id)
        
        # Commit to database
        await test_db.commit()
        
        # Phase 2: Query database directly (bypassing agent)
        result = await test_db.execute(
            select(DBConversation).where(DBConversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        
        # Verify data is in database
        assert conv is not None
        assert conv.title == "Persistence Test"
        assert conv.user_id == "test-user-persist"
        assert conv.message_count >= 2  # At least user + assistant messages
    
    @pytest.mark.asyncio
    async def test_user_isolation(self, test_db):
        """Test that different users' conversations are isolated."""
        from core.agent import CeliaAgent
        
        # Create conversations for two different users
        agent_user1 = CeliaAgent(db=test_db, user_id="user-1")
        conv1 = await agent_user1.create_conversation("User 1's Conversation")
        await agent_user1.process_message("Hello from user 1", conv1)
        
        agent_user2 = CeliaAgent(db=test_db, user_id="user-2")
        conv2 = await agent_user2.create_conversation("User 2's Conversation")
        await agent_user2.process_message("Hello from user 2", conv2)
        
        # Commit to database
        await test_db.commit()
        
        # Verify user 1 can only see their conversations
        user1_convs = await agent_user1.list_conversations()
        assert len(user1_convs) == 1
        assert user1_convs[0]["id"] == conv1
        
        # Verify user 2 can only see their conversations
        user2_convs = await agent_user2.list_conversations()
        assert len(user2_convs) == 1
        assert user2_convs[0]["id"] == conv2
    
    @pytest.mark.asyncio
    async def test_multiple_messages_in_conversation(self, test_db):
        """Test that multiple messages are correctly stored."""
        from core.agent import CeliaAgent
        
        agent = CeliaAgent(db=test_db, user_id="test-user-multi")
        conv_id = await agent.create_conversation("Multi-Message Test")
        
        # Send multiple messages
        messages = [
            "Hello",
            "How are you?",
            "What can you do?",
        ]
        
        for msg in messages:
            await agent.process_message(msg, conv_id)
        
        # Commit to database
        await test_db.commit()
        
        # Retrieve history
        history = await agent.get_conversation_history(conv_id)
        
        # Count user messages (excluding system messages)
        user_msgs = [m for m in history if m["role"] == "user"]
        assert len(user_msgs) == 3
        
        # Verify all messages are present
        contents = [m["content"] for m in user_msgs]
        assert "Hello" in contents
        assert "How are you?" in contents
        assert "What can you do?" in contents
    
    @pytest.mark.asyncio
    async def test_conversation_not_found_returns_empty(self, test_db):
        """Test that requesting non-existent conversation returns empty."""
        from core.agent import CeliaAgent
        
        agent = CeliaAgent(db=test_db, user_id="test-user-empty")
        
        # Try to get history for non-existent conversation
        history = await agent.get_conversation_history("non-existent-id")
        assert history == []
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_without_db(self):
        """Test that agent still works without database (backward compatibility)."""
        from core.agent import CeliaAgent
        
        # Create agent without database
        agent = CeliaAgent()
        
        # Should still be able to create conversation
        conv_id = await agent.create_conversation("Legacy Test")
        assert conv_id is not None
        
        # Should be able to process message
        response = await agent.process_message("Hello legacy", conv_id)
        assert response is not None
        assert response.content is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
