"""
Data Migration Service for celia.pro
Handles migration from file-based storage to PostgreSQL
"""

import json
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Conversation, Message
from database.repositories import (
    UserRepository, ConversationRepository, 
    MessageRepository
)
from core.memory import ShortTermMemory, LongTermMemory

logger = logging.getLogger(__name__)


class DataMigrationService:
    """Service for migrating data from file-based storage to PostgreSQL"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)
    
    async def migrate_conversations(
        self,
        user_id: str,
        file_conversations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Migrate conversations from agent memory to PostgreSQL
        
        Args:
            user_id: Target user ID
            file_conversations: Conversations dict from agent.conversations
        
        Returns:
            Migration statistics
        """
        stats = {
            "conversations_migrated": 0,
            "messages_migrated": 0,
            "errors": []
        }
        
        for conv_id, conv_data in file_conversations.items():
            try:
                # Check if already migrated
                existing = await self.conv_repo.get_by_id(conv_id)
                if existing:
                    logger.info(f"Conversation {conv_id} already exists, skipping")
                    continue
                
                # Create conversation
                conversation = Conversation(
                    id=conv_id,
                    user_id=user_id,
                    title=conv_data.get("title", "Migrated Conversation"),
                    description=conv_data.get("description"),
                    is_archived=conv_data.get("is_archived", False),
                    is_pinned=conv_data.get("is_pinned", False),
                    message_count=len(conv_data.get("messages", [])),
                    total_tokens_used=conv_data.get("total_tokens_used", 0),
                    created_at=conv_data.get("created_at", datetime.now(timezone.utc)),
                    updated_at=conv_data.get("updated_at", datetime.now(timezone.utc))
                )
                
                self.session.add(conversation)
                await self.session.flush()
                stats["conversations_migrated"] += 1
                
                # Migrate messages
                for msg_data in conv_data.get("messages", []):
                    try:
                        message = Message(
                            id=msg_data.get("id"),
                            conversation_id=conv_id,
                            role=msg_data.get("role", "user"),
                            content=msg_data.get("content", ""),
                            tool_calls=msg_data.get("tool_calls"),
                            tool_results=msg_data.get("tool_results"),
                            steps=msg_data.get("steps"),
                            tokens_used=msg_data.get("tokens_used", 0),
                            model_used=msg_data.get("model_used"),
                            provider_used=msg_data.get("provider_used"),
                            created_at=msg_data.get("timestamp", datetime.now(timezone.utc))
                        )
                        
                        self.session.add(message)
                        stats["messages_migrated"] += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to migrate message in {conv_id}: {str(e)}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)
                
            except Exception as e:
                error_msg = f"Failed to migrate conversation {conv_id}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        await self.session.commit()
        logger.info(f"Migration complete: {stats}")
        return stats
    
    async def migrate_long_term_memory(
        self,
        user_id: str,
        memory_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Migrate long-term memory to PostgreSQL
        
        Args:
            user_id: Target user ID
            memory_data: Memory data from LongTermMemory
        
        Returns:
            Migration statistics
        """
        stats = {
            "memories_migrated": 0,
            "errors": []
        }
        
        # Create a special conversation for memory
        memory_conv = Conversation(
            user_id=user_id,
            title="Long-term Memory",
            description="Migrated long-term memory entries",
            is_archived=False,
            is_pinned=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self.session.add(memory_conv)
        await self.session.flush()
        
        # Migrate memories as messages
        memories = memory_data.get("memories", {})
        for key, memory in memories.items():
            try:
                content = json.dumps({
                    "key": key,
                    "value": memory.get("value"),
                    "category": memory.get("category", "general"),
                    "created_at": memory.get("created_at"),
                    "updated_at": memory.get("updated_at")
                }, ensure_ascii=False)
                
                message = Message(
                    conversation_id=memory_conv.id,
                    role="system",
                    content=content,
                    created_at=memory.get("created_at", datetime.now(timezone.utc))
                )
                
                self.session.add(message)
                stats["memories_migrated"] += 1
                
            except Exception as e:
                error_msg = f"Failed to migrate memory {key}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        # Migrate knowledge base
        knowledge_items = memory_data.get("knowledge_base", [])
        for item in knowledge_items:
            try:
                content = json.dumps({
                    "type": "knowledge",
                    "content": item.get("content"),
                    "source": item.get("source"),
                    "tags": item.get("tags", []),
                    "created_at": item.get("created_at")
                }, ensure_ascii=False)
                
                message = Message(
                    conversation_id=memory_conv.id,
                    role="system",
                    content=content,
                    created_at=item.get("created_at", datetime.now(timezone.utc))
                )
                
                self.session.add(message)
                stats["memories_migrated"] += 1
                
            except Exception as e:
                error_msg = f"Failed to migrate knowledge item: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        await self.session.commit()
        logger.info(f"Memory migration complete: {stats}")
        return stats
    
    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all user data from PostgreSQL
        
        Args:
            user_id: User ID to export
        
        Returns:
            Complete user data dict
        """
        # Get user conversations
        conversations = await self.conv_repo.get_user_conversations(
            user_id, include_archived=True
        )
        
        export_data = {
            "user_id": user_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "conversations": []
        }
        
        for conv in conversations:
            conv_data = {
                "id": conv.id,
                "title": conv.title,
                "description": conv.description,
                "is_archived": conv.is_archived,
                "is_pinned": conv.is_pinned,
                "message_count": conv.message_count,
                "total_tokens_used": conv.total_tokens_used,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "messages": []
            }
            
            # Get messages
            messages = await self.msg_repo.get_conversation_messages(conv.id)
            for msg in messages:
                msg_data = {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": msg.tool_calls,
                    "tool_results": msg.tool_results,
                    "steps": msg.steps,
                    "tokens_used": msg.tokens_used,
                    "model_used": msg.model_used,
                    "provider_used": msg.provider_used,
                    "timestamp": msg.created_at.isoformat()
                }
                conv_data["messages"].append(msg_data)
            
            export_data["conversations"].append(conv_data)
        
        return export_data
    
    async def import_user_data(
        self,
        user_id: str,
        data: Dict[str, Any],
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Import user data into PostgreSQL
        
        Args:
            user_id: Target user ID
            data: Data dict from export
            overwrite: Whether to overwrite existing data
        
        Returns:
            Import statistics
        """
        if overwrite:
            # Delete existing conversations
            conversations = await self.conv_repo.get_user_conversations(
                user_id, include_archived=True
            )
            for conv in conversations:
                await self.conv_repo.delete(conv)
            await self.session.commit()
        
        # Migrate conversations
        file_conversations = {}
        for conv_data in data.get("conversations", []):
            conv_id = conv_data["id"]
            file_conversations[conv_id] = {
                "title": conv_data.get("title"),
                "description": conv_data.get("description"),
                "is_archived": conv_data.get("is_archived", False),
                "is_pinned": conv_data.get("is_pinned", False),
                "total_tokens_used": conv_data.get("total_tokens_used", 0),
                "created_at": datetime.fromisoformat(conv_data["created_at"]),
                "updated_at": datetime.fromisoformat(conv_data["updated_at"]),
                "messages": []
            }
            
            for msg_data in conv_data.get("messages", []):
                file_conversations[conv_id]["messages"].append({
                    "id": msg_data["id"],
                    "role": msg_data["role"],
                    "content": msg_data["content"],
                    "tool_calls": msg_data.get("tool_calls"),
                    "tool_results": msg_data.get("tool_results"),
                    "steps": msg_data.get("steps"),
                    "tokens_used": msg_data.get("tokens_used", 0),
                    "model_used": msg_data.get("model_used"),
                    "provider_used": msg_data.get("provider_used"),
                    "timestamp": datetime.fromisoformat(msg_data["timestamp"])
                })
        
        return await self.migrate_conversations(user_id, file_conversations)


class MemoryBridge:
    """
    Bridge between file-based memory and PostgreSQL
    Allows gradual migration while maintaining compatibility
    """
    
    def __init__(self, session: AsyncSession, user_id: str):
        self.session = session
        self.user_id = user_id
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)
    
    async def get_recent_context(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent messages for context"""
        messages = await self.msg_repo.get_recent_messages(
            conversation_id, limit
        )
        
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    
    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        **kwargs
    ) -> Message:
        """Save a message to PostgreSQL"""
        return await self.msg_repo.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            **kwargs
        )
    
    async def search_memories(self, query: str, limit: int = 10) -> List[Dict]:
        """Search in long-term memory (stored as system messages)"""
        # Find memory conversation
        result = await self.session.execute(
            select(Conversation).where(
                and_(
                    Conversation.user_id == self.user_id,
                    Conversation.title == "Long-term Memory"
                )
            )
        )
        memory_conv = result.scalar_one_or_none()
        
        if not memory_conv:
            return []
        
        # Search in messages
        messages = await self.msg_repo.get_conversation_messages(memory_conv.id)
        
        results = []
        for msg in messages:
            try:
                data = json.loads(msg.content)
                # Simple text search
                if query.lower() in msg.content.lower():
                    results.append(data)
                    if len(results) >= limit:
                        break
            except:
                continue
        
        return results


# Import helper
from sqlalchemy import select, and_
