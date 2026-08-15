"""
Tests for celia.pro Phase 2 components
Tests for Data Isolation Middleware and Admin API
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

# Test Data Isolation Middleware
from middleware.data_isolation import (
    DataIsolationMiddleware,
    OwnershipVerifier,
    DataIsolationLogger,
    DataIsolationError
)


class TestDataIsolation:
    """Test data isolation components"""
    
    def test_middleware_creation(self):
        """Test creating data isolation middleware"""
        app = MagicMock()
        middleware = DataIsolationMiddleware(app)
        
        assert middleware.app == app
    
    def test_ownership_verifier_creation(self):
        """Test creating ownership verifier"""
        db = MagicMock()
        verifier = OwnershipVerifier(db)
        
        assert verifier.db == db
    
    @pytest.mark.asyncio
    async def test_verify_conversation(self):
        """Test conversation ownership verification"""
        db = MagicMock()
        verifier = OwnershipVerifier(db)
        
        # Mock conversation
        mock_conv = MagicMock()
        mock_conv.user_id = "user123"
        
        verifier.conv_repo = MagicMock()
        verifier.conv_repo.get_by_id = AsyncMock(return_value=mock_conv)
        
        # Verify ownership
        result = await verifier.verify_conversation("conv123", "user123")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_conversation_wrong_user(self):
        """Test conversation ownership verification with wrong user"""
        db = MagicMock()
        verifier = OwnershipVerifier(db)
        
        # Mock conversation with different user
        mock_conv = MagicMock()
        mock_conv.user_id = "user456"
        
        verifier.conv_repo = MagicMock()
        verifier.conv_repo.get_by_id = AsyncMock(return_value=mock_conv)
        
        # Verify ownership (should fail)
        result = await verifier.verify_conversation("conv123", "user123")
        
        assert result is False
    
    def test_data_isolation_logger(self):
        """Test data isolation logger"""
        # Log successful access
        DataIsolationLogger.log_access_attempt(
            user_id="user123",
            resource_type="conversation",
            resource_id="conv123",
            success=True,
            ip_address="127.0.0.1"
        )
        
        # Log failed access
        DataIsolationLogger.log_access_attempt(
            user_id="user123",
            resource_type="conversation",
            resource_id="conv456",
            success=False,
            ip_address="127.0.0.1"
        )
    
    def test_data_isolation_error(self):
        """Test data isolation error"""
        error = DataIsolationError(
            message="Access denied",
            user_id="user123",
            resource_id="conv456"
        )
        
        assert error.message == "Access denied"
        assert error.user_id == "user123"
        assert error.resource_id == "conv456"


# Test Admin API Models
from api.admin import (
    UserUpdateRequest,
    UserStatsResponse,
    SystemStatsResponse,
    AuditLogResponse
)


class TestAdminModels:
    """Test admin API models"""
    
    def test_user_update_request(self):
        """Test user update request model"""
        request = UserUpdateRequest(
            display_name="New Name",
            role="admin",
            is_active=True,
            daily_request_limit=100
        )
        
        assert request.display_name == "New Name"
        assert request.role == "admin"
        assert request.daily_request_limit == 100
    
    def test_user_stats_response(self):
        """Test user stats response model"""
        response = UserStatsResponse(
            id="user123",
            email="test@example.com",
            username="testuser",
            display_name="Test User",
            role="user",
            is_active=True,
            created_at="2024-01-01T00:00:00",
            last_login="2024-01-02T00:00:00",
            daily_request_limit=50,
            daily_requests_used=10,
            conversations_count=5,
            messages_count=100,
            total_tokens_used=5000
        )
        
        assert response.id == "user123"
        assert response.conversations_count == 5
        assert response.total_tokens_used == 5000
    
    def test_system_stats_response(self):
        """Test system stats response model"""
        response = SystemStatsResponse(
            total_users=100,
            active_users=80,
            total_conversations=500,
            total_messages=10000,
            total_tokens_used=500000,
            failed_actions_24h=5,
            new_users_24h=10,
            new_conversations_24h=20
        )
        
        assert response.total_users == 100
        assert response.active_users == 80
        assert response.failed_actions_24h == 5
    
    def test_audit_log_response(self):
        """Test audit log response model"""
        response = AuditLogResponse(
            id="log123",
            user_id="user123",
            action="login",
            resource_type="user",
            resource_id="user123",
            details={"ip": "127.0.0.1"},
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
            success=True,
            error_message=None,
            created_at="2024-01-01T00:00:00"
        )
        
        assert response.id == "log123"
        assert response.action == "login"
        assert response.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
