"""
celia.pro Database Connection
==============================
Async database connection with SQLAlchemy 2.0 and connection pooling.
Supports PostgreSQL (production) and SQLite (development/testing).
"""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker
)
from sqlalchemy.pool import AsyncAdaptedQueuePool
from contextlib import asynccontextmanager
import logging

from database.models import Base

logger = logging.getLogger(__name__)


# ============= DATABASE CONFIGURATION =============

class DatabaseConfig:
    """Database configuration loaded from environment."""
    
    # Connection URL (PostgreSQL for production, SQLite for dev)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./celia_dev.db"  # Default: SQLite for development
    )
    
    # Connection pool settings
    POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    # Retry settings
    MAX_RETRIES: int = int(os.getenv("DB_MAX_RETRIES", "3"))
    RETRY_DELAY: int = int(os.getenv("DB_RETRY_DELAY", "5"))


# ============= ENGINE SETUP =============

class DatabaseManager:
    """
    Manages database connections and sessions.
    Supports async operations with connection pooling.
    """
    
    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig()
        self._engine = None
        self._session_factory = None
    
    async def initialize(self):
        """Initialize database engine and create tables."""
        try:
            # Determine pool class based on database type
            if "postgresql" in self.config.DATABASE_URL:
                pool_class = AsyncAdaptedQueuePool
                pool_kwargs = {
                    "poolclass": pool_class,
                    "pool_size": self.config.POOL_SIZE,
                    "max_overflow": self.config.MAX_OVERFLOW,
                    "pool_timeout": self.config.POOL_TIMEOUT,
                    "pool_recycle": self.config.POOL_RECYCLE,
                }
            else:
                # SQLite doesn't support pooling
                pool_kwargs = {}
            
            engine_kwargs = {
                "echo": os.getenv("DB_ECHO", "false").lower() == "true",
            }
            engine_kwargs.update(pool_kwargs)

            # asyncpg does not accept sslmode in the URL query string when
            # using a connection pool; move it to connect_args instead.
            if "postgresql" in self.config.DATABASE_URL:
                # asyncpg does not accept sslmode/channel_binding in the URL
                # query string; pass them as driver-level connect args.
                # NOTE: asyncpg does not support channel_binding — use ssl="require".
                import urllib.parse
                parsed = urllib.parse.urlparse(self.config.DATABASE_URL)
                qs = urllib.parse.parse_qs(parsed.query)
                sslmode = qs.get("sslmode", ["prefer"])[0]
                if sslmode != "disable":
                    engine_kwargs["connect_args"] = {"ssl": "require"}
                clean_qs = {k: v for k, v in qs.items() if k not in ("sslmode", "channel_binding")}
                cleaned = parsed._replace(query=urllib.parse.urlencode(clean_qs, doseq=True))
                self.config.DATABASE_URL = urllib.parse.urlunparse(cleaned)

            # Create async engine
            self._engine = create_async_engine(
                self.config.DATABASE_URL,
                **engine_kwargs
            )
            
            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            
            # Create tables (for development; use Alembic in production)
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info(f"Database initialized: {self.config.DATABASE_URL.split('@')[-1] if '@' in self.config.DATABASE_URL else 'sqlite'}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.
        Usage:
            async with db.get_session() as session:
                # use session
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def session_scope(self):
        """
        Context manager for database sessions.
        Usage:
            async with db.session_scope() as session:
                # use session
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
    
    async def health_check(self) -> dict:
        """Check database health."""
        try:
            async with self.session_scope() as session:
                # Simple query to test connection
                from sqlalchemy import text
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()  # scalar() returns int, not awaitable
                
                return {
                    "status": "healthy",
                    "database": self.config.DATABASE_URL.split("@")[-1] if "@" in self.config.DATABASE_URL else "sqlite",
                    "pool_size": self.config.POOL_SIZE,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database": self.config.DATABASE_URL.split("@")[-1] if "@" in self.config.DATABASE_URL else "sqlite",
            }


# ============= GLOBAL INSTANCE =============

# Create global database manager instance
db_manager = DatabaseManager()


# ============= DEPENDENCY INJECTION =============

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    Usage in endpoints:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # use db session
    """
    async with db_manager.session_scope() as session:
        yield session
