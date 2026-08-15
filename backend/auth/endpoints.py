"""
celia.pro Auth API Endpoints
=============================
Authentication and user management REST API.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import re
import logging

from database.connection import get_db
from database.models import User
from auth.auth import (
    authenticate_user, create_user, create_access_token, 
    create_refresh_token, get_current_user, refresh_access_token,
    AuthConfig
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ============= REQUEST MODELS =============

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User profile response."""
    id: str
    email: str
    username: str
    display_name: Optional[str]
    role: str
    is_verified: bool
    created_at: str
    quota: dict


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ============= ENDPOINTS =============

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    
    - Creates user with hashed password
    - Returns JWT access and refresh tokens
    - Email must be unique
    - Username must be unique
    """
    try:
        # Validate password strength
        if len(request.password) < AuthConfig.PASSWORD_MIN_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at least {AuthConfig.PASSWORD_MIN_LENGTH} characters"
            )
        
        # Create user
        user = await create_user(
            db=db,
            email=request.email,
            username=request.username,
            password=request.password,
            display_name=request.display_name
        )
        
        # Generate tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        logger.info(f"User registered: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with email and password.
    
    - Validates credentials
    - Returns JWT tokens
    - Updates last_login timestamp
    """
    # Authenticate user
    user = await authenticate_user(db, request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    from datetime import datetime, timezone
    user.last_login = datetime.now(timezone.utc)
    await db.flush()
    
    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    logger.info(f"User logged in: {user.email}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh access token using refresh token.
    
    - Validates refresh token
    - Returns new access and refresh tokens
    - Old tokens remain valid until expiration
    """
    try:
        tokens = await refresh_access_token(db, request.refresh_token)
        
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's profile.
    
    - Requires valid JWT token
    - Returns user information and quota
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role.value,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat(),
        quota={
            "daily_limit": current_user.daily_request_limit,
            "daily_used": current_user.daily_requests_used,
            "remaining": current_user.daily_request_limit - current_user.daily_requests_used
        }
    )


@router.put("/me/password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user's password.
    
    - Requires current password verification
    - Hashes and stores new password
    - Does not invalidate existing tokens
    """
    from auth.auth import verify_password, get_password_hash
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(request.new_password) < AuthConfig.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"New password must be at least {AuthConfig.PASSWORD_MIN_LENGTH} characters"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    await db.flush()
    
    logger.info(f"Password changed for user: {current_user.email}")
    
    return {"message": "Password changed successfully"}


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout current user.
    
    - Client should discard tokens
    - Server-side token invalidation requires Redis (future enhancement)
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return {"message": "Logged out successfully"}


# ============= ADMIN ENDPOINTS =============

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all users (admin only).
    
    - Requires admin role
    - Returns paginated user list
    """
    from auth.auth import require_admin
    await require_admin(current_user)
    
    from sqlalchemy import select
    result = await db.execute(
        select(User)
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            is_verified=user.is_verified,
            created_at=user.created_at.isoformat(),
            quota={
                "daily_limit": user.daily_request_limit,
                "daily_used": user.daily_requests_used,
                "remaining": user.daily_request_limit - user.daily_requests_used
            }
        )
        for user in users
    ]
