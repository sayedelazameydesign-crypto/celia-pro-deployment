"""
celia.pro Authentication Tests
===============================
Comprehensive tests for JWT authentication, user management, and security.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole
from auth.auth import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, authenticate_user,
    create_user, get_user_by_email, check_user_quota,
    AuthConfig
)
from jose import JWTError


# ============= FIXTURES =============

@pytest.fixture
def test_password():
    return "testpass123"


@pytest.fixture
def test_user_data():
    return {
        "email": "test@celia.pro",
        "username": "testuser",
        "password": "testpass123",
        "display_name": "Test User"
    }


@pytest.fixture
def sample_jwt_payload():
    return {
        "sub": "user-123",
        "email": "test@celia.pro",
        "role": "user"
    }


# ============= PASSWORD HASHING TESTS =============

class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_password_hashing(self, test_password):
        """Test that passwords are hashed correctly."""
        hashed = get_password_hash(test_password)
        
        # Hash should be different from plain text
        assert hashed != test_password
        
        # Hash should be a valid bcrypt hash
        assert hashed.startswith("$2b$")
        
        # Hash should verify correctly
        assert verify_password(test_password, hashed) is True
    
    def test_password_verification_wrong_password(self, test_password):
        """Test that wrong passwords fail verification."""
        hashed = get_password_hash(test_password)
        
        # Wrong password should fail
        assert verify_password("wrong_password", hashed) is False
    
    def test_password_hashing_uniqueness(self, test_password):
        """Test that same password produces different hashes."""
        hash1 = get_password_hash(test_password)
        hash2 = get_password_hash(test_password)
        
        # Same password should produce different hashes (salt)
        assert hash1 != hash2
        
        # But both should verify
        assert verify_password(test_password, hash1) is True
        assert verify_password(test_password, hash2) is True


# ============= JWT TOKEN TESTS =============

class TestJWTTokens:
    """Test JWT token creation and validation."""
    
    def test_create_access_token(self, sample_jwt_payload):
        """Test access token creation."""
        token = create_access_token(data=sample_jwt_payload)
        
        # Token should be a string
        assert isinstance(token, str)
        
        # Token should have 3 parts (header.payload.signature)
        assert len(token.split(".")) == 3
    
    def test_decode_access_token(self, sample_jwt_payload):
        """Test access token decoding."""
        token = create_access_token(data=sample_jwt_payload)
        decoded = decode_token(token)
        
        # Decoded payload should match original
        assert decoded["sub"] == sample_jwt_payload["sub"]
        assert decoded["email"] == sample_jwt_payload["email"]
        assert decoded["role"] == sample_jwt_payload["role"]
        assert "exp" in decoded
    
    def test_create_refresh_token(self, sample_jwt_payload):
        """Test refresh token creation."""
        token = create_refresh_token(data=sample_jwt_payload)
        decoded = decode_token(token)
        
        # Refresh token should have type="refresh"
        assert decoded["type"] == "refresh"
    
    def test_expired_token(self, sample_jwt_payload):
        """Test that expired tokens raise JWTError."""
        token = create_access_token(
            data=sample_jwt_payload,
            expires_delta=timedelta(hours=-1)
        )
        
        # Decoding should raise error
        with pytest.raises(JWTError):
            decode_token(token)
    
    def test_invalid_token(self):
        """Test that invalid tokens raise JWTError."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(JWTError):
            decode_token(invalid_token)
    
    def test_token_with_custom_expiration(self, sample_jwt_payload):
        """Test token with custom expiration time."""
        custom_delta = timedelta(minutes=30)
        token = create_access_token(
            data=sample_jwt_payload,
            expires_delta=custom_delta
        )
        
        decoded = decode_token(token)
        
        # Expiration should be approximately 30 minutes from now
        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        expected_time = datetime.now(timezone.utc) + custom_delta
        
        # Allow 5 second tolerance
        assert abs((exp_time - expected_time).total_seconds()) < 5


# ============= USER MANAGEMENT TESTS =============

class TestUserManagement:
    """Test user creation and management."""
    
    @pytest.mark.asyncio
    async def test_create_user(self, test_user_data):
        """Test user creation."""
        # Mock database session
        mock_db = MagicMock(spec=AsyncSession)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        
        # Mock query results - user doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Create user
        user = await create_user(
            db=mock_db,
            email=test_user_data["email"],
            username=test_user_data["username"],
            password=test_user_data["password"],
            display_name=test_user_data["display_name"]
        )
        
        # Verify user object
        assert user.email == test_user_data["email"]
        assert user.username == test_user_data["username"]
        assert user.display_name == test_user_data["display_name"]
        assert user.role == UserRole.USER
        assert user.is_active is True
        
        # Password should be hashed
        assert user.hashed_password != test_user_data["password"]
        assert verify_password(test_user_data["password"], user.hashed_password)
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, test_user_data):
        """Test that duplicate email raises ValueError."""
        mock_db = MagicMock(spec=AsyncSession)
        
        # Mock existing user
        existing_user = User(
            id="existing-user",
            email=test_user_data["email"],
            username="existing",
            hashed_password="hashed"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Email already registered"):
            await create_user(
                db=mock_db,
                email=test_user_data["email"],
                username="different_username",
                password=test_user_data["password"]
            )
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, test_user_data):
        """Test successful user authentication."""
        mock_db = MagicMock(spec=AsyncSession)
        
        # Create user with hashed password
        user = User(
            id="test-user-id",
            email=test_user_data["email"],
            username=test_user_data["username"],
            hashed_password=get_password_hash(test_user_data["password"]),
            is_active=True
        )
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Authenticate
        authenticated_user = await authenticate_user(
            db=mock_db,
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        
        # Should return user
        assert authenticated_user is not None
        assert authenticated_user.id == "test-user-id"
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, test_user_data):
        """Test authentication with wrong password."""
        mock_db = MagicMock(spec=AsyncSession)
        
        # Create user
        user = User(
            id="test-user-id",
            email=test_user_data["email"],
            username=test_user_data["username"],
            hashed_password=get_password_hash(test_user_data["password"]),
            is_active=True
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Authenticate with wrong password
        authenticated_user = await authenticate_user(
            db=mock_db,
            email=test_user_data["email"],
            password="wrong_password"
        )
        
        # Should return None
        assert authenticated_user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, test_user_data):
        """Test authentication of inactive user."""
        mock_db = MagicMock(spec=AsyncSession)
        
        # Create inactive user
        user = User(
            id="test-user-id",
            email=test_user_data["email"],
            username=test_user_data["username"],
            hashed_password=get_password_hash(test_user_data["password"]),
            is_active=False  # Inactive
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Authenticate
        authenticated_user = await authenticate_user(
            db=mock_db,
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        
        # Should return None (inactive user)
        assert authenticated_user is None


# ============= QUOTA MANAGEMENT TESTS =============

class TestQuotaManagement:
    """Test user quota management."""
    
    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self):
        """Test quota check within limit."""
        user = User(
            id="test-user",
            email="test@celia.pro",
            username="testuser",
            hashed_password="hashed",
            daily_request_limit=50,
            daily_requests_used=10,
            last_request_reset=datetime.now(timezone.utc)
        )
        
        has_quota = await check_user_quota(user)
        assert has_quota is True
    
    @pytest.mark.asyncio
    async def test_check_quota_exceeded(self):
        """Test quota check when exceeded."""
        user = User(
            id="test-user",
            email="test@celia.pro",
            username="testuser",
            hashed_password="hashed",
            daily_request_limit=50,
            daily_requests_used=50,
            last_request_reset=datetime.now(timezone.utc)
        )
        
        has_quota = await check_user_quota(user)
        assert has_quota is False
    
    @pytest.mark.asyncio
    async def test_quota_reset_on_new_day(self):
        """Test that quota resets on new day."""
        # User who used quota yesterday
        user = User(
            id="test-user",
            email="test@celia.pro",
            username="testuser",
            hashed_password="hashed",
            daily_request_limit=50,
            daily_requests_used=50,
            last_request_reset=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        has_quota = await check_user_quota(user)
        
        # Should have quota after reset
        assert has_quota is True
        assert user.daily_requests_used == 0
    
    @pytest.mark.asyncio
    async def test_quota_reset_when_none(self):
        """Test that quota resets when last_request_reset is None."""
        user = User(
            id="test-user",
            email="test@celia.pro",
            username="testuser",
            hashed_password="hashed",
            daily_request_limit=50,
            daily_requests_used=50,
            last_request_reset=None
        )
        
        has_quota = await check_user_quota(user)
        
        # Should have quota after reset
        assert has_quota is True
        assert user.daily_requests_used == 0


# ============= SECURITY TESTS =============

class TestAuthSecurity:
    """Test authentication security."""
    
    def test_password_min_length(self):
        """Test password minimum length requirement."""
        assert AuthConfig.PASSWORD_MIN_LENGTH >= 8
    
    def test_jwt_secret_not_empty(self):
        """Test that JWT secret is not empty."""
        assert len(AuthConfig.SECRET_KEY) > 0
    
    def test_token_algorithm_secure(self):
        """Test that JWT uses secure algorithm."""
        assert AuthConfig.ALGORITHM in ["HS256", "HS384", "HS512"]
    
    def test_bcrypt_rounds_secure(self):
        """Test that bcrypt uses sufficient rounds."""
        assert AuthConfig.BCRYPT_ROUNDS >= 12


# ============= INTEGRATION TESTS =============

class TestAuthIntegration:
    """Integration tests for authentication flow."""
    
    @pytest.mark.asyncio
    async def test_full_auth_flow(self, test_user_data):
        """Test complete authentication flow: register -> login -> access."""
        mock_db = MagicMock(spec=AsyncSession)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        
        # Mock user doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # 1. Register
        user = await create_user(
            db=mock_db,
            email=test_user_data["email"],
            username=test_user_data["username"],
            password=test_user_data["password"]
        )
        
        # 2. Create tokens (ensure user_id is string)
        user_id = str(user.id)
        access_token = create_access_token(data={"sub": user_id})
        refresh_token = create_refresh_token(data={"sub": user_id})
        
        # 3. Decode tokens
        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)
        
        # 4. Verify
        assert access_payload["sub"] == user_id
        assert refresh_payload["type"] == "refresh"
        
        # 5. Simulate protected endpoint access
        assert access_payload["sub"] == user_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
