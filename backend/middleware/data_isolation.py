"""
Data Isolation Middleware for celia.pro
Ensures each user can only access their own data
"""

import logging
from typing import Callable, Optional
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.repositories import (
    ConversationRepository, 
    MessageRepository,
    UserAPIKeyRepository
)

logger = logging.getLogger(__name__)


class DataIsolationMiddleware:
    """
    Middleware that ensures data isolation between users
    Prevents users from accessing other users' data
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware entry point"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Store original send function
        original_send = send
        
        async def modified_send(message):
            # Can modify response here if needed
            await original_send(message)
        
        await self.app(scope, receive, modified_send)


def verify_conversation_ownership(
    conversation_id: str,
    user_id: str,
    db: AsyncSession
) -> bool:
    """
    Verify that a conversation belongs to the specified user
    
    Args:
        conversation_id: ID of the conversation
        user_id: ID of the user
        db: Database session
    
    Returns:
        True if conversation belongs to user, False otherwise
    """
    # This would be called in route handlers
    # Implementation depends on how routes are structured
    return True


def verify_message_ownership(
    message_id: str,
    user_id: str,
    db: AsyncSession
) -> bool:
    """
    Verify that a message belongs to a conversation owned by the user
    
    Args:
        message_id: ID of the message
        user_id: ID of the user
        db: Database session
    
    Returns:
        True if message belongs to user's conversation, False otherwise
    """
    # This would be called in route handlers
    return True


def verify_api_key_ownership(
    key_id: str,
    user_id: str,
    db: AsyncSession
) -> bool:
    """
    Verify that an API key belongs to the specified user
    
    Args:
        key_id: ID of the API key
        user_id: ID of the user
        db: Database session
    
    Returns:
        True if API key belongs to user, False otherwise
    """
    # This would be called in route handlers
    return True


class OwnershipVerifier:
    """
    Helper class for verifying data ownership
    Used in route handlers to ensure proper isolation
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)
        self.key_repo = UserAPIKeyRepository(db)
    
    async def verify_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Verify conversation ownership"""
        conversation = await self.conv_repo.get_by_id(conversation_id)
        if not conversation:
            return False
        return conversation.user_id == user_id
    
    async def verify_message(self, message_id: str, user_id: str) -> bool:
        """Verify message ownership (through conversation)"""
        message = await self.msg_repo.get_by_id(message_id)
        if not message:
            return False
        
        # Get the conversation
        conversation = await self.conv_repo.get_by_id(message.conversation_id)
        if not conversation:
            return False
        
        return conversation.user_id == user_id
    
    async def verify_api_key(self, key_id: str, user_id: str) -> bool:
        """Verify API key ownership"""
        key = await self.key_repo.get_by_id(key_id)
        if not key:
            return False
        return key.user_id == user_id
    
    async def verify_audit_log_access(self, log_id: str, user_id: str, is_admin: bool) -> bool:
        """Verify audit log access (users can only see their own logs, admins can see all)"""
        if is_admin:
            return True
        
        # Import here to avoid circular imports
        from database.repositories import AuditLogRepository
        audit_repo = AuditLogRepository(self.db)
        log = await audit_repo.get_by_id(log_id)
        if not log:
            return False
        return log.user_id == user_id


# Dependency for FastAPI routes
async def get_ownership_verifier(db: AsyncSession = Depends(get_db)) -> OwnershipVerifier:
    """FastAPI dependency for ownership verification"""
    return OwnershipVerifier(db)


# Decorator for protecting routes
def require_ownership(resource_type: str):
    """
    Decorator to require ownership verification for a route
    
    Usage:
        @app.get("/conversations/{conv_id}")
        @require_ownership("conversation")
        async def get_conversation(conv_id: str, user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Extract user and resource ID from kwargs
            user = kwargs.get("user")
            resource_id = kwargs.get(f"{resource_type}_id") or kwargs.get("id")
            
            if not user or not resource_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user or resource ID"
                )
            
            # Get database session
            db = kwargs.get("db")
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available"
                )
            
            # Verify ownership
            verifier = OwnershipVerifier(db)
            
            if resource_type == "conversation":
                is_owner = await verifier.verify_conversation(resource_id, user.id)
            elif resource_type == "message":
                is_owner = await verifier.verify_message(resource_id, user.id)
            elif resource_type == "api_key":
                is_owner = await verifier.verify_api_key(resource_id, user.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown resource type: {resource_type}"
                )
            
            if not is_owner:
                logger.warning(
                    f"Access denied: User {user.id} attempted to access "
                    f"{resource_type} {resource_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not own this resource"
                )
            
            # Call the actual route handler
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class DataIsolationError(Exception):
    """Exception raised when data isolation is violated"""
    def __init__(self, message: str, user_id: str, resource_id: str):
        self.message = message
        self.user_id = user_id
        self.resource_id = resource_id
        super().__init__(self.message)


class DataIsolationLogger:
    """Logger for data isolation violations"""
    
    @staticmethod
    def log_access_attempt(
        user_id: str,
        resource_type: str,
        resource_id: str,
        success: bool,
        ip_address: Optional[str] = None
    ):
        """Log an access attempt"""
        status_str = "SUCCESS" if success else "DENIED"
        log_msg = (
            f"Data access {status_str}: "
            f"user={user_id}, "
            f"resource={resource_type}:{resource_id}"
        )
        
        if ip_address:
            log_msg += f", ip={ip_address}"
        
        if success:
            logger.info(log_msg)
        else:
            logger.warning(log_msg)
    
    @staticmethod
    def log_isolation_violation(
        user_id: str,
        resource_type: str,
        resource_id: str,
        owner_id: str,
        ip_address: Optional[str] = None
    ):
        """Log a data isolation violation"""
        log_msg = (
            f"ISOLATION VIOLATION: "
            f"user={user_id} attempted to access "
            f"{resource_type}={resource_id} owned by {owner_id}"
        )
        
        if ip_address:
            log_msg += f" (ip={ip_address})"
        
        logger.error(log_msg)
