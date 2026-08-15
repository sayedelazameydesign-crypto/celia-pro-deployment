"""
Integration Tests: Memory Store Upgrade (P1-5)
================================================
Tests the advanced memory system with vectors, metadata, TTL, and semantic search.
Uses isolated database per test.
"""

import pytest
import pytest_asyncio
import os
import asyncio

from fastapi.testclient import TestClient
from database.models import User, UserRole, MemoryItem
from auth.auth import get_password_hash, create_access_token
from datetime import datetime, timezone, timedelta


@pytest_asyncio.fixture
async def memory_client(isolated_db, disable_rate_limiter):
    """Create test client with isolated database for memory tests."""
    from api.main import app
    from database.connection import get_db
    
    session, engine = isolated_db
    
    # Create test user
    test_user = User(
        id="memory-test-user",
        email="memory_user@example.com",
        username="memoryuser",
        hashed_password=get_password_hash("securepass123"),
        role=UserRole.USER,
        is_active=True,
    )
    session.add(test_user)
    await session.commit()
    
    # Create token
    token = create_access_token(data={"sub": "memory-test-user", "type": "access"})
    
    async def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    import api.main
    original_auth = api.main.AUTH_REQUIRED
    api.main.AUTH_REQUIRED = True
    
    client = TestClient(app)
    
    yield client, session, token
    
    app.dependency_overrides.clear()
    api.main.AUTH_REQUIRED = original_auth


@pytest_asyncio.fixture
async def unauth_client(isolated_db, disable_rate_limiter):
    """Create test client without auth for unauthorized tests."""
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


class TestMemoryStoreAndRetrieve:
    """Test basic memory storage and retrieval."""
    
    @pytest.mark.asyncio
    async def test_store_memory_basic(self, memory_client):
        """Test storing a basic memory."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post(
            "/api/memory/store",
            json={
                "key": "test_fact",
                "value": "The sky is blue",
                "type": "fact",
                "category": "science",
                "tags": ["nature", "sky"],
                "importance": 0.8
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stored"
        assert data["key"] == "test_fact"
        assert data["has_vector"] is True
        
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_retrieve_memory_by_key(self, memory_client):
        """Test retrieving a memory by key."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        # Store memory
        client.post(
            "/api/memory/store",
            json={
                "key": "retrieve_test",
                "value": "Test value",
                "type": "fact"
            },
            headers=headers
        )
        await db_session.commit()
        
        # Retrieve memory
        response = client.get("/api/memory/retrieve_test", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "retrieve_test"
        assert data["value"] == "Test value"
        assert data["type"] == "fact"
        assert "metadata" in data
        assert "state" in data
    
    @pytest.mark.asyncio
    async def test_memory_not_found(self, memory_client):
        """Test retrieving non-existent memory."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/memory/nonexistent_key", headers=headers)
        assert response.status_code == 404


class TestMemoryVectorSearch:
    """Test vector-based semantic search."""
    
    @pytest.mark.asyncio
    async def test_search_by_vector(self, memory_client):
        """Test searching memories by vector similarity."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        # Store multiple memories
        memories = [
            {"key": "python_fact", "value": "Python is a programming language", "type": "fact"},
            {"key": "java_fact", "value": "Java is also a programming language", "type": "fact"},
            {"key": "cooking_fact", "value": "Cooking requires heat and ingredients", "type": "fact"}
        ]
        
        for mem in memories:
            client.post("/api/memory/store", json=mem, headers=headers)
        
        await db_session.commit()
        
        # Search with vector similarity
        response = client.get(
            "/api/memory/search",
            params={
                "query": "programming languages",
                "use_vector_search": True,
                "limit": 2
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 2
        assert data["search_strategy"] == "vector_similarity"


class TestMemoryMetadataSearch:
    """Test metadata-based search."""
    
    @pytest.mark.asyncio
    async def test_search_by_category(self, memory_client):
        """Test searching memories by category."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        # Store memories with different categories
        client.post(
            "/api/memory/store",
            json={
                "key": "science_fact",
                "value": "Science fact",
                "type": "fact",
                "category": "science"
            },
            headers=headers
        )
        
        client.post(
            "/api/memory/store",
            json={
                "key": "art_fact",
                "value": "Art fact",
                "type": "fact",
                "category": "art"
            },
            headers=headers
        )
        
        await db_session.commit()
        
        # Search by category
        response = client.get(
            "/api/memory/search",
            params={"category": "science"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) >= 1
        for result in data["results"]:
            assert result["metadata"]["category"] == "science"


class TestMemoryTTL:
    """Test TTL (Time-To-Live) functionality."""
    
    @pytest.mark.asyncio
    async def test_memory_with_ttl(self, memory_client):
        """Test storing memory with TTL."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post(
            "/api/memory/store",
            json={
                "key": "temporary_fact",
                "value": "This will expire",
                "type": "fact",
                "ttl_seconds": 3600
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["expires_at"] is not None
        
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_expired_memory_not_returned(self, memory_client):
        """Test that expired memories are not returned."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        # Store memory with past expiration
        from database.repositories import MemoryRepository
        
        mem_repo = MemoryRepository(db_session)
        await mem_repo.store_memory(
            user_id="memory-test-user",
            key="expired_memory",
            value="This is expired",
            type="fact",
            ttl_seconds=-3600  # Expired 1 hour ago
        )
        await db_session.commit()
        
        # Try to retrieve expired memory
        response = client.get("/api/memory/expired_memory", headers=headers)
        assert response.status_code == 404


class TestMemoryDelete:
    """Test memory deletion."""
    
    @pytest.mark.asyncio
    async def test_delete_memory(self, memory_client):
        """Test deleting a memory."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        # Store memory
        client.post(
            "/api/memory/store",
            json={
                "key": "to_delete",
                "value": "Delete me",
                "type": "fact"
            },
            headers=headers
        )
        await db_session.commit()
        
        # Delete memory
        response = client.delete("/api/memory/to_delete", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        
        await db_session.commit()
        
        # Verify deletion
        response = client.get("/api/memory/to_delete", headers=headers)
        assert response.status_code == 404


class TestMemoryCleanup:
    """Test memory cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_memories(self, memory_client):
        """Test cleaning up expired memories."""
        client, db_session, token = memory_client
        headers = {"Authorization": f"Bearer {token}"}
        
        # Store expired memories
        from database.repositories import MemoryRepository
        
        mem_repo = MemoryRepository(db_session)
        for i in range(3):
            await mem_repo.store_memory(
                user_id="memory-test-user",
                key=f"expired_{i}",
                value=f"Expired memory {i}",
                type="fact",
                ttl_seconds=-3600
            )
        
        await db_session.commit()
        
        # Cleanup
        response = client.post("/api/memory/cleanup", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleaned"
        assert data["deleted_count"] == 3


class TestMemoryAPI:
    """Test API endpoints with authentication."""
    
    @pytest.mark.asyncio
    async def test_unauthorized_store_memory(self, unauth_client):
        """Test that storing memory requires authentication."""
        client, db_session = unauth_client
        
        response = client.post(
            "/api/memory/store",
            json={
                "key": "test",
                "value": "test",
                "type": "fact"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_unauthorized_search_memory(self, unauth_client):
        """Test that searching memory requires authentication."""
        client, db_session = unauth_client
        
        response = client.get("/api/memory/search", params={"query": "test"})
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
