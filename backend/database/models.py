"""
celia.pro Database Models
==========================
SQLAlchemy models for multi-tenant data storage.
Supports PostgreSQL with asyncpg for production performance.
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, 
    JSON, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base
import uuid
from datetime import datetime
import enum

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class UserRole(enum.Enum):
    """User roles for authorization."""
    USER = "user"
    ADMIN = "admin"
    GUEST = "guest"


class User(Base):
    """
    User model with authentication and quota management.
    Each user has isolated data (conversations, files, API keys).
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile
    display_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Role & Status
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Quotas & Limits (for free tier management)
    daily_request_limit = Column(Integer, default=50, nullable=False)
    daily_requests_used = Column(Integer, default=0, nullable=False)
    last_request_reset = Column(DateTime(timezone=True), default=func.now())
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("UserAPIKey", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_users_email_active', 'email', 'is_active'),
    )


class Conversation(Base):
    """
    Conversation model - isolated per user.
    Contains metadata and relationship to messages.
    """
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Metadata
    title = Column(String(200), default="New Conversation", nullable=False)
    description = Column(Text, nullable=True)
    
    # Status
    is_archived = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    
    # Statistics
    message_count = Column(Integer, default=0, nullable=False)
    total_tokens_used = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", 
                           order_by="Message.created_at")
    
    __table_args__ = (
        Index('idx_conversations_user_active', 'user_id', 'is_archived'),
        Index('idx_conversations_updated', 'updated_at'),
    )


class Message(Base):
    """
    Message model - part of a conversation.
    Supports multi-modal content and tool calls.
    """
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Content
    role = Column(String(20), nullable=False)  # "user", "assistant", "system", "tool"
    content = Column(Text, nullable=False)
    
    # Tool calls (JSON structure)
    tool_calls = Column(JSON, nullable=True)  # List of tool calls made
    tool_results = Column(JSON, nullable=True)  # Results from tool executions
    
    # Steps/Plan (for agent transparency)
    steps = Column(JSON, nullable=True)  # Execution steps
    
    # Token usage
    tokens_used = Column(Integer, default=0, nullable=False)
    
    # Metadata
    model_used = Column(String(50), nullable=True)  # "gemini-2.0-flash"
    provider_used = Column(String(20), nullable=True)  # "gemini" or "huggingface"
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    __table_args__ = (
        Index('idx_messages_conversation_created', 'conversation_id', 'created_at'),
    )


class UserAPIKey(Base):
    """
    User's API keys for LLM providers.
    Stored encrypted, never returned to client.
    """
    __tablename__ = "user_api_keys"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Provider info
    provider = Column(String(20), nullable=False)  # "gemini" or "huggingface"
    key_name = Column(String(100), nullable=False)  # User-friendly name
    encrypted_key = Column(Text, nullable=False)  # AES-256 encrypted
    
    # Configuration
    model = Column(String(100), nullable=True)  # "gemini-2.0-flash"
    is_active = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    
    # Usage tracking
    requests_made = Column(Integer, default=0, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_used = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'provider', 'key_name', name='uq_user_provider_keyname'),
        Index('idx_api_keys_user_active', 'user_id', 'is_active'),
    )


class AuditLog(Base):
    """
    Audit log for security and compliance.
    Tracks all significant actions in the system.
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Action info
    action = Column(String(100), nullable=False, index=True)  # "login", "tool_execution", etc.
    resource_type = Column(String(50), nullable=True)  # "conversation", "message", "api_key"
    resource_id = Column(String, nullable=True)
    
    # Details
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Result
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_created', 'created_at'),
    )


class MemoryItem(Base):
    """
    Advanced memory storage with semantic search capabilities.
    Supports vector embeddings, metadata filtering, and TTL.
    """
    __tablename__ = "memory_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core fields
    key = Column(String(255), nullable=False, index=True)  # Unique identifier
    value = Column(JSON, nullable=False)  # Can be string or complex JSON
    type = Column(String(50), nullable=False)  # "fact", "lesson", "preference", "context"
    
    # Metadata for filtering (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    memory_metadata = Column(JSON, nullable=True)  # {category, tags, importance, ttl_seconds, expires_at}
    
    # Vector embeddings for semantic search (256 dimensions)
    # Using JSON for SQLite compatibility; PostgreSQL would use pgvector
    vector_256 = Column(JSON, nullable=True)  # List of 256 floats
    
    # State tracking
    state = Column(JSON, nullable=True)  # {created_at, updated_at, last_accessed_at, access_count, version}
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='uq_user_memory_key'),
        Index('idx_memory_user_key', 'user_id', 'key'),
        Index('idx_memory_expires', 'expires_at'),
    )


# ============= MIGRATION HELPERS =============

def init_db(engine):
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def drop_db(engine):
    """Drop all tables (DANGER: Data loss!)."""
    Base.metadata.drop_all(bind=engine)
