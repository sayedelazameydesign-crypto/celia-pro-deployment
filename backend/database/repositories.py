"""
Repository Layer for celia.pro
Implements data access patterns for all database entities
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from database.models import (
    User, Conversation, Message, UserAPIKey, AuditLog, UserRole, MemoryItem
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common CRUD operations"""
    
    def __init__(self, session: AsyncSession, model):
        self.session = session
        self.model = model
    
    async def get_by_id(self, id: str) -> Optional[Any]:
        """Get entity by ID"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Any]:
        """Get all entities with pagination"""
        result = await self.session.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create(self, entity: Any) -> Any:
        """Create new entity"""
        self.session.add(entity)
        await self.session.flush()
        return entity
    
    async def update(self, entity: Any) -> Any:
        """Update entity"""
        await self.session.flush()
        return entity
    
    async def delete(self, entity: Any) -> None:
        """Delete entity"""
        await self.session.delete(entity)
        await self.session.flush()


class UserRepository(BaseRepository):
    """Repository for User operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all active users"""
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_admin_users(self) -> List[User]:
        """Get all admin users"""
        result = await self.session.execute(
            select(User).where(User.role == UserRole.ADMIN)
        )
        return result.scalars().all()
    
    async def search_users(self, query: str, limit: int = 20) -> List[User]:
        """Search users by email or username"""
        result = await self.session.execute(
            select(User)
            .where(
                or_(
                    User.email.ilike(f"%{query}%"),
                    User.username.ilike(f"%{query}%"),
                    User.display_name.ilike(f"%{query}%")
                )
            )
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        # Count conversations
        conv_result = await self.session.execute(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user_id)
        )
        conv_count = conv_result.scalar()
        
        # Count messages
        msg_result = await self.session.execute(
            select(func.count(Message.id))
            .join(Conversation)
            .where(Conversation.user_id == user_id)
        )
        msg_count = msg_result.scalar()
        
        # Total tokens used
        token_result = await self.session.execute(
            select(func.sum(Conversation.total_tokens_used))
            .where(Conversation.user_id == user_id)
        )
        total_tokens = token_result.scalar() or 0
        
        return {
            "conversations_count": conv_count,
            "messages_count": msg_count,
            "total_tokens_used": total_tokens
        }


class ConversationRepository(BaseRepository):
    """Repository for Conversation operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Conversation)
    
    async def get_user_conversations(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 50,
        include_archived: bool = False
    ) -> List[Conversation]:
        """Get all conversations for a user"""
        query = select(Conversation).where(Conversation.user_id == user_id)
        
        if not include_archived:
            query = query.where(Conversation.is_archived == False)
        
        query = query.order_by(desc(Conversation.updated_at)).offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_conversation_with_messages(
        self, 
        conversation_id: str,
        user_id: str
    ) -> Optional[Conversation]:
        """Get conversation with all messages (for a specific user)"""
        result = await self.session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def search_conversations(
        self, 
        user_id: str, 
        query: str,
        limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by title"""
        result = await self.session.execute(
            select(Conversation)
            .where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.title.ilike(f"%{query}%")
                )
            )
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def archive_conversation(
        self, 
        conversation_id: str,
        user_id: str
    ) -> bool:
        """Archive a conversation"""
        conv = await self.get_by_id(conversation_id)
        if conv and conv.user_id == user_id:
            conv.is_archived = True
            await self.session.flush()
            return True
        return False
    
    async def pin_conversation(
        self,
        conversation_id: str,
        user_id: str,
        pin: bool = True
    ) -> bool:
        """Pin/unpin a conversation"""
        conv = await self.get_by_id(conversation_id)
        if conv and conv.user_id == user_id:
            conv.is_pinned = pin
            await self.session.flush()
            return True
        return False
    
    async def get_pinned_conversations(self, user_id: str) -> List[Conversation]:
        """Get all pinned conversations for a user"""
        result = await self.session.execute(
            select(Conversation)
            .where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.is_pinned == True
                )
            )
            .order_by(desc(Conversation.updated_at))
        )
        return result.scalars().all()


class MessageRepository(BaseRepository):
    """Repository for Message operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Message)
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """Get all messages in a conversation"""
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[Message]:
        """Get recent messages from a conversation"""
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))  # Return in chronological order
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        tool_results: Optional[List[Dict]] = None,
        steps: Optional[List[Dict]] = None,
        tokens_used: int = 0,
        model_used: Optional[str] = None,
        provider_used: Optional[str] = None
    ) -> Message:
        """Add a message to a conversation"""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            steps=steps,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used
        )
        self.session.add(message)
        await self.session.flush()
        
        # Update conversation stats
        conv_result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one()
        conversation.message_count += 1
        conversation.total_tokens_used += tokens_used
        conversation.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        
        return message
    
    async def get_message_context(
        self,
        conversation_id: str,
        message_id: str,
        context_size: int = 5
    ) -> List[Message]:
        """Get context around a specific message"""
        # Get the target message first
        target = await self.get_by_id(message_id)
        if not target or target.conversation_id != conversation_id:
            return []
        
        # Get messages around it
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        all_messages = result.scalars().all()
        
        # Find index and get context
        try:
            idx = next(i for i, m in enumerate(all_messages) if m.id == message_id)
            start = max(0, idx - context_size)
            end = min(len(all_messages), idx + context_size + 1)
            return all_messages[start:end]
        except StopIteration:
            return []


class UserAPIKeyRepository(BaseRepository):
    """Repository for UserAPIKey operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, UserAPIKey)
    
    async def get_user_keys(self, user_id: str) -> List[UserAPIKey]:
        """Get all API keys for a user"""
        result = await self.session.execute(
            select(UserAPIKey)
            .where(
                and_(
                    UserAPIKey.user_id == user_id,
                    UserAPIKey.is_active == True
                )
            )
        )
        return result.scalars().all()
    
    async def get_active_key(
        self,
        user_id: str,
        provider: str
    ) -> Optional[UserAPIKey]:
        """Get the active primary key for a provider"""
        result = await self.session.execute(
            select(UserAPIKey)
            .where(
                and_(
                    UserAPIKey.user_id == user_id,
                    UserAPIKey.provider == provider,
                    UserAPIKey.is_active == True,
                    UserAPIKey.is_primary == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def add_key(
        self,
        user_id: str,
        provider: str,
        key_name: str,
        encrypted_key: str,
        model: Optional[str] = None,
        is_primary: bool = False
    ) -> UserAPIKey:
        """Add a new API key for a user"""
        # If setting as primary, unset other primaries for this provider
        if is_primary:
            result = await self.session.execute(
                select(UserAPIKey)
                .where(
                    and_(
                        UserAPIKey.user_id == user_id,
                        UserAPIKey.provider == provider,
                        UserAPIKey.is_primary == True
                    )
                )
            )
            existing_primary = result.scalar_one_or_none()
            if existing_primary:
                existing_primary.is_primary = False
        
        key = UserAPIKey(
            user_id=user_id,
            provider=provider,
            key_name=key_name,
            encrypted_key=encrypted_key,
            model=model,
            is_primary=is_primary
        )
        self.session.add(key)
        await self.session.flush()
        return key
    
    async def update_usage(
        self,
        key_id: str,
        tokens_used: int
    ) -> None:
        """Update key usage statistics"""
        key = await self.get_by_id(key_id)
        if key:
            key.requests_made += 1
            key.tokens_used += tokens_used
            key.last_used = datetime.now(timezone.utc)
            await self.session.flush()
    
    async def deactivate_key(
        self,
        key_id: str,
        user_id: str
    ) -> bool:
        """Deactivate an API key"""
        key = await self.get_by_id(key_id)
        if key and key.user_id == user_id:
            key.is_active = False
            await self.session.flush()
            return True
        return False


class AuditLogRepository(BaseRepository):
    """Repository for AuditLog operations"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditLog)
    
    async def log_action(
        self,
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Log an action"""
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )
        self.session.add(log)
        await self.session.flush()
        return log
    
    async def get_user_logs(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs for a user"""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_action_logs(
        self,
        action: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get logs for a specific action type"""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_failed_logs(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get all failed action logs"""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.success == False)
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


class MemoryRepository(BaseRepository):
    """Repository for MemoryItem operations with semantic search support"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, MemoryItem)
    
    async def store_memory(
        self,
        user_id: str,
        key: str,
        value: Any,
        type: str,
        metadata: Optional[Dict] = None,
        vector_256: Optional[List[float]] = None,
        ttl_seconds: Optional[int] = None
    ) -> MemoryItem:
        """Store a new memory item or update existing one"""
        from database.models import MemoryItem
        
        # Check if memory already exists
        result = await self.session.execute(
            select(MemoryItem).where(
                and_(
                    MemoryItem.user_id == user_id,
                    MemoryItem.key == key
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        # Calculate expires_at from TTL
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        # Prepare metadata with defaults
        if metadata is None:
            metadata = {}
        metadata.setdefault('importance', 1.0)
        metadata.setdefault('version', 1)
        
        # Prepare state
        now = datetime.now(timezone.utc)
        state = {
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'last_accessed_at': now.isoformat(),
            'access_count': 0,
            'version': metadata.get('version', 1)
        }
        
        if existing:
            # Update existing memory
            existing.value = value
            existing.type = type
            existing.memory_metadata = metadata
            existing.vector_256 = vector_256
            existing.state = state
            existing.expires_at = expires_at
            existing.updated_at = now
            await self.session.flush()
            return existing
        else:
            # Create new memory
            memory = MemoryItem(
                user_id=user_id,
                key=key,
                value=value,
                type=type,
                memory_metadata=metadata,
                vector_256=vector_256,
                state=state,
                expires_at=expires_at
            )
            self.session.add(memory)
            await self.session.flush()
            return memory
    
    async def retrieve_memory(self, user_id: str, key: str) -> Optional[MemoryItem]:
        """Retrieve a memory by key, checking expiration"""
        from database.models import MemoryItem
        
        result = await self.session.execute(
            select(MemoryItem).where(
                and_(
                    MemoryItem.user_id == user_id,
                    MemoryItem.key == key
                )
            )
        )
        memory = result.scalar_one_or_none()
        
        if memory:
            # Check if expired
            if memory.expires_at:
                # Handle both timezone-aware and naive datetimes
                now = datetime.now(timezone.utc)
                expires_at = memory.expires_at
                if expires_at.tzinfo is None:
                    # If naive, assume UTC
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now:
                    return None
            
            # Update access stats
            if memory.state:
                memory.state['last_accessed_at'] = datetime.now(timezone.utc).isoformat()
                memory.state['access_count'] = memory.state.get('access_count', 0) + 1
                await self.session.flush()
        
        return memory
    
    async def search_by_vector(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 5
    ) -> List[MemoryItem]:
        """Search memories by vector similarity (cosine similarity)"""
        from database.models import MemoryItem
        import numpy as np
        
        # Get all non-expired memories for this user with vectors
        result = await self.session.execute(
            select(MemoryItem).where(
                and_(
                    MemoryItem.user_id == user_id,
                    MemoryItem.vector_256.isnot(None),
                    or_(
                        MemoryItem.expires_at.is_(None),
                        MemoryItem.expires_at > datetime.now(timezone.utc)
                    )
                )
            )
        )
        memories = result.scalars().all()
        
        if not memories or not query_vector:
            return []
        
        # Calculate cosine similarity
        query_vec = np.array(query_vector)
        query_norm = np.linalg.norm(query_vec)
        
        if query_norm == 0:
            return []
        
        similarities = []
        for memory in memories:
            if memory.vector_256:
                mem_vec = np.array(memory.vector_256)
                mem_norm = np.linalg.norm(mem_vec)
                
                if mem_norm == 0:
                    continue
                
                # Cosine similarity
                similarity = np.dot(query_vec, mem_vec) / (query_norm * mem_norm)
                similarities.append((similarity, memory))
        
        # Sort by similarity (descending) and return top results
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in similarities[:limit]]
    
    async def search_by_metadata(
        self,
        user_id: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        type: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryItem]:
        """Search memories by metadata fields"""
        from database.models import MemoryItem
        from sqlalchemy import cast, String
        
        query = select(MemoryItem).where(
            and_(
                MemoryItem.user_id == user_id,
                or_(
                    MemoryItem.expires_at.is_(None),
                    MemoryItem.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        
        # Filter by type
        if type:
            query = query.where(MemoryItem.type == type)
        
        # Filter by category (JSON field)
        if category:
            # For SQLite, we use JSON extraction
            query = query.where(
                func.json_extract(MemoryItem.memory_metadata, '$.category') == category
            )
        
        # Filter by tags (JSON array)
        if tags:
            # Check if any of the tags are in the metadata.tags array
            for tag in tags:
                query = query.where(
                    func.json_extract(MemoryItem.memory_metadata, '$.tags').like(f'%"{tag}"%')
                )
        
        query = query.order_by(desc(MemoryItem.created_at)).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def delete_memory(self, user_id: str, key: str) -> bool:
        """Delete a memory by key"""
        from database.models import MemoryItem
        
        result = await self.session.execute(
            select(MemoryItem).where(
                and_(
                    MemoryItem.user_id == user_id,
                    MemoryItem.key == key
                )
            )
        )
        memory = result.scalar_one_or_none()
        
        if memory:
            await self.session.delete(memory)
            await self.session.flush()
            return True
        return False
    
    async def cleanup_expired(self) -> int:
        """Remove all expired memories, returns count of deleted items"""
        from database.models import MemoryItem
        
        now = datetime.now(timezone.utc)
        
        result = await self.session.execute(
            select(MemoryItem).where(
                and_(
                    MemoryItem.expires_at.isnot(None),
                    MemoryItem.expires_at < now
                )
            )
        )
        expired_memories = result.scalars().all()
        count = len(expired_memories)
        
        for memory in expired_memories:
            await self.session.delete(memory)
        
        await self.session.flush()
        return count


# Factory functions for dependency injection
def get_user_repository(session: AsyncSession) -> UserRepository:
    return UserRepository(session)

def get_conversation_repository(session: AsyncSession) -> ConversationRepository:
    return ConversationRepository(session)

def get_message_repository(session: AsyncSession) -> MessageRepository:
    return MessageRepository(session)

def get_api_key_repository(session: AsyncSession) -> UserAPIKeyRepository:
    return UserAPIKeyRepository(session)

def get_audit_log_repository(session: AsyncSession) -> AuditLogRepository:
    return AuditLogRepository(session)

def get_memory_repository(session: AsyncSession) -> MemoryRepository:
    return MemoryRepository(session)
