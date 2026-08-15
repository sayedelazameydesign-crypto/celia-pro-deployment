"""
Admin Dashboard API for celia.pro
Provides administrative endpoints for managing users, monitoring system, and analytics
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database.connection import get_db
from database.models import User, UserRole, Conversation, Message, AuditLog
from database.repositories import (
    UserRepository, ConversationRepository,
    MessageRepository, AuditLogRepository
)
from auth.auth import get_current_user, require_admin
from core.agent_safety import CostTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============= REQUEST/RESPONSE MODELS =============

class UserUpdateRequest(BaseModel):
    """Request model for updating user"""
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    daily_request_limit: Optional[int] = None


class UserStatsResponse(BaseModel):
    """Response model for user statistics"""
    id: str
    email: str
    username: str
    display_name: Optional[str]
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str]
    daily_request_limit: int
    daily_requests_used: int
    conversations_count: int
    messages_count: int
    total_tokens_used: int


class SystemStatsResponse(BaseModel):
    """Response model for system statistics"""
    total_users: int
    active_users: int
    total_conversations: int
    total_messages: int
    total_tokens_used: int
    failed_actions_24h: int
    new_users_24h: int
    new_conversations_24h: int


class AuditLogResponse(BaseModel):
    """Response model for audit log entry"""
    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: str


# ============= USER MANAGEMENT =============

@router.get("/users", response_model=List[UserStatsResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List all users with filtering and pagination
    Admin only endpoint
    """
    user_repo = UserRepository(db)
    
    # Build query
    from sqlalchemy import select
    query = select(User)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    if role:
        query = query.where(User.role == role)
    
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") |
            User.username.ilike(f"%{search}%") |
            User.display_name.ilike(f"%{search}%")
        )
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Get stats for each user
    response = []
    for user in users:
        stats = await user_repo.get_user_stats(user.id)
        
        response.append(UserStatsResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None,
            daily_request_limit=user.daily_request_limit,
            daily_requests_used=user.daily_requests_used,
            conversations_count=stats["conversations_count"],
            messages_count=stats["messages_count"],
            total_tokens_used=stats["total_tokens_used"]
        ))
    
    return response


@router.get("/users/{user_id}", response_model=UserStatsResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed user information
    Admin only endpoint
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    stats = await user_repo.get_user_stats(user.id)
    
    return UserStatsResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
        daily_request_limit=user.daily_request_limit,
        daily_requests_used=user.daily_requests_used,
        conversations_count=stats["conversations_count"],
        messages_count=stats["messages_count"],
        total_tokens_used=stats["total_tokens_used"]
    )


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    update: UserUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user information
    Admin only endpoint
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if update.display_name is not None:
        user.display_name = update.display_name
    
    if update.role is not None:
        try:
            user.role = UserRole(update.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {update.role}"
            )
    
    if update.is_active is not None:
        user.is_active = update.is_active
    
    if update.daily_request_limit is not None:
        user.daily_request_limit = update.daily_request_limit
    
    await db.flush()
    
    logger.info(f"Admin {current_user.id} updated user {user_id}")
    
    return {"message": "User updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user and all their data
    Admin only endpoint - USE WITH CAUTION
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete user (cascade will delete conversations, messages, etc.)
    await user_repo.delete(user)
    await db.commit()
    
    logger.warning(f"Admin {current_user.id} deleted user {user_id}")
    
    return {"message": "User deleted successfully"}


@router.post("/users/{user_id}/reset-quota")
async def reset_user_quota(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset user's daily quota
    Admin only endpoint
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.daily_requests_used = 0
    user.last_request_reset = datetime.now(timezone.utc)
    await db.flush()
    
    logger.info(f"Admin {current_user.id} reset quota for user {user_id}")
    
    return {"message": "Quota reset successfully"}


# ============= SYSTEM STATISTICS =============

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system-wide statistics
    Admin only endpoint
    """
    from sqlalchemy import select, func, and_
    
    # Total users
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar()
    
    # Active users
    result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = result.scalar()
    
    # Total conversations
    result = await db.execute(select(func.count(Conversation.id)))
    total_conversations = result.scalar()
    
    # Total messages
    result = await db.execute(select(func.count(Message.id)))
    total_messages = result.scalar()
    
    # Total tokens used
    result = await db.execute(
        select(func.sum(Conversation.total_tokens_used))
    )
    total_tokens = result.scalar() or 0
    
    # Failed actions in last 24h
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.success == False,
                AuditLog.created_at >= yesterday
            )
        )
    )
    failed_actions_24h = result.scalar()
    
    # New users in last 24h
    result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= yesterday)
    )
    new_users_24h = result.scalar()
    
    # New conversations in last 24h
    result = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= yesterday)
    )
    new_conversations_24h = result.scalar()
    
    return SystemStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_tokens_used=total_tokens,
        failed_actions_24h=failed_actions_24h,
        new_users_24h=new_users_24h,
        new_conversations_24h=new_conversations_24h
    )


@router.get("/stats/tokens")
async def get_token_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get token usage statistics over time
    Admin only endpoint
    """
    from sqlalchemy import select, func, and_, cast, Date
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get daily token usage
    result = await db.execute(
        select(
            cast(Conversation.created_at, Date).label('date'),
            func.sum(Conversation.total_tokens_used).label('tokens')
        )
        .where(Conversation.created_at >= start_date)
        .group_by(cast(Conversation.created_at, Date))
        .order_by(cast(Conversation.created_at, Date))
    )
    
    daily_stats = [
        {"date": str(row.date), "tokens": row.tokens or 0}
        for row in result
    ]
    
    # Get provider breakdown
    result = await db.execute(
        select(
            Message.provider_used,
            func.sum(Message.tokens_used)
        )
        .where(Message.created_at >= start_date)
        .group_by(Message.provider_used)
    )
    
    provider_stats = {
        row.provider_used or "unknown": row.sum or 0
        for row in result
    }
    
    return {
        "period_days": days,
        "daily_usage": daily_stats,
        "provider_breakdown": provider_stats,
        "total_tokens": sum(d["tokens"] for d in daily_stats)
    }


# ============= AUDIT LOGS =============

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs with filtering
    Admin only endpoint
    """
    audit_repo = AuditLogRepository(db)
    
    from sqlalchemy import select, and_
    query = select(AuditLog)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    if action:
        query = query.where(AuditLog.action == action)
    
    if success is not None:
        query = query.where(AuditLog.success == success)
    
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
    
    query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]


@router.get("/audit-logs/failed")
async def get_failed_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get failed audit logs
    Admin only endpoint
    """
    audit_repo = AuditLogRepository(db)
    logs = await audit_repo.get_failed_logs(skip, limit)
    
    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]


# ============= SYSTEM HEALTH =============

@router.get("/health/detailed")
async def get_detailed_health(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed system health information
    Admin only endpoint
    """
    from database.connection import db_manager
    
    # Database health
    db_health = await db_manager.health_check()
    
    # Get counts
    from sqlalchemy import select, func
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    
    result = await db.execute(select(func.count(Conversation.id)))
    conv_count = result.scalar()
    
    result = await db.execute(select(func.count(Message.id)))
    msg_count = result.scalar()
    
    return {
        "database": db_health,
        "counts": {
            "users": user_count,
            "conversations": conv_count,
            "messages": msg_count
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/system/config")
async def get_system_config(
    current_user: User = Depends(require_admin)
):
    """
    Get system configuration (non-sensitive)
    Admin only endpoint
    """
    from core.security import SecurityConfig
    from auth.auth import AuthConfig
    
    config = SecurityConfig()
    
    return {
        "rate_limit": {
            "requests": config.rate_limit_requests,
            "window_seconds": config.rate_limit_window
        },
        "max_request_size": config.max_request_size,
        "max_message_length": config.max_message_length,
        "max_code_length": config.max_code_length,
        "cors_origins": config.cors_origins,
        "auth": {
            "token_expire_minutes": AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_expire_days": AuthConfig.REFRESH_TOKEN_EXPIRE_DAYS,
            "password_min_length": AuthConfig.PASSWORD_MIN_LENGTH
        }
    }
