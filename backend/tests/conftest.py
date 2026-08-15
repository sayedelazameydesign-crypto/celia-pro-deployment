"""
Shared test fixtures for celia.pro tests.
Ensures complete test isolation with per-test database.
"""

import pytest
import asyncio
import os
import pytest_asyncio
from unittest.mock import patch


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Disable rate limiter for all tests."""
    from api.main import rate_limiter
    original_is_allowed = rate_limiter.is_allowed
    
    # Mock rate limiter to always allow
    def mock_is_allowed(client_id):
        return True, 0
    
    rate_limiter.is_allowed = mock_is_allowed
    
    yield
    
    # Restore original
    rate_limiter.is_allowed = original_is_allowed


@pytest_asyncio.fixture(scope="function")
async def isolated_db(tmp_path):
    """Create a completely isolated database for each test."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from database.models import Base
    
    # Use unique database file per test
    db_path = tmp_path / f"test_{id(tmp_path)}.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    
    # Create engine
    engine = create_async_engine(db_url, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create session
    async with session_factory() as session:
        yield session, engine
    
    # Cleanup
    await engine.dispose()
    
    # Remove database file
    if db_path.exists():
        try:
            db_path.unlink()
        except:
            pass


@pytest_asyncio.fixture
async def db_session():
    """Get a database session for a single test."""
    from database.connection import db_manager
    
    async with db_manager.session_scope() as session:
        yield session


@pytest.fixture
def mock_valid_user():
    """Create a mock valid user for auth tests."""
    from database.models import User, UserRole
    user = User(
        id="test-user-123",
        email="test@celia.pro",
        username="testuser",
        hashed_password="hashed",
        display_name="Test User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        daily_request_limit=50,
        daily_requests_used=0,
    )
    return user


@pytest.fixture
def valid_token():
    """Create a valid JWT token."""
    from auth.auth import create_access_token
    return create_access_token(data={"sub": "test-user-123", "type": "access"})


@pytest.fixture
def mock_db_session():
    """Create mock database session that yields properly."""
    from unittest.mock import MagicMock
    
    mock_session = MagicMock()
    
    async def mock_get_db():
        yield mock_session
    
    return mock_get_db
