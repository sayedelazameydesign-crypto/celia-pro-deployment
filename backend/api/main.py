"""
celia.pro API
==============
FastAPI application with REST and WebSocket endpoints.
Supports Gemini API and HuggingFace Inference API (free tiers).
Includes: Rate limiting, input validation, CORS hardening, health checks.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import asyncio
import json
import logging
import os
import sys
import time
import uuid

# Import exception handlers
from core.exceptions import (
    NovaMindException,
    novamind_exception_handler,
    validation_exception_handler,
    database_error_handler,
    integrity_error_handler,
    generic_exception_handler,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError as NovaMindValidationError,
    RateLimitError
)

# Add parent to path

from core.agent import CeliaAgent
from core.llm_clients import GeminiClient, GroqClient, HuggingFaceClient, LLMRouter
from core.security import (
    SecurityConfig, RateLimiter, InputValidator, RequestContext,
    PromptInjectionDetector, mask_secret, sanitize_error_for_client, ValidationError
)
from core.tool_security import policy_engine
from core.agent_safety import CostTracker, StructuredLogger
from models.schemas import AgentConfig
from database.connection import db_manager, get_db
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Auth and Admin systems (v3.0.0)
try:
    from auth.endpoints import router as auth_router
    from api.admin import router as admin_router
    from auth.auth import get_current_user
    AUTH_AVAILABLE = True
except ImportError as e:
    AUTH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"Auth/Admin modules not available - {e}")

# Track application start time for uptime calculation
_app_start_time = time.time()

# ============= STRUCTURED LOGGING SETUP =============

# Initialize structured logging (JSON format for production)
from monitoring.structured_logger import setup_structured_logging, MonitoringLogger

setup_structured_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    json_output=os.getenv("LOG_FORMAT", "json").lower() == "json",
)

logger = MonitoringLogger.get_logger("api.main")


# ============= LIFESPAN (STARTUP/SHUTDOWN) =============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown."""
    # Startup
    logger.info("Starting up celia.pro...")
    
    # Initialize database
    try:
        await db_manager.initialize()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Continue without database for now (backward compatibility)
    
    yield
    
    # Shutdown
    logger.info("Shutting down celia.pro...")
    await db_manager.close()
    logger.info("✅ Database connections closed")

# ============= APP INITIALIZATION =============

app = FastAPI(
    title="celia.pro AI Agent",
    description="Advanced multi-tool AI agent system powered by celia.pro with Gemini & HuggingFace support",
    version="3.1.0",
    lifespan=lifespan,  # Add lifespan manager for startup/shutdown
)

# ============= MONITORING SETUP =============

# Prometheus metrics
from monitoring.prometheus_metrics import setup_prometheus, PrometheusMetrics

setup_prometheus(app, endpoint="/metrics")

# Sentry error tracking (optional - only activates if SENTRY_DSN is set)
from monitoring.sentry_integration import setup_sentry

setup_sentry()

# Register exception handlers
app.add_exception_handler(NovaMindException, novamind_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Security configuration
security_config = SecurityConfig()

# CORS - hardened (no wildcard in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)

# Core components (shared, non-db state)
rate_limiter = RateLimiter(
    max_requests=security_config.rate_limit_requests,
    window_seconds=security_config.rate_limit_window
)
validator = InputValidator(security_config)
cost_tracker = CostTracker()
active_connections: Dict[str, WebSocket] = {}

# Shared LLM configuration (persists across requests)
_shared_llm_config = {}

# Legacy agent for backward compatibility (when db is not available)
_legacy_agent = CeliaAgent()


async def get_agent(db: Optional[AsyncSession] = None, user_id: Optional[str] = None) -> CeliaAgent:
    """
    Create a CeliaAgent instance with database session and user context.
    
    If db is provided, uses database for persistence.
    Otherwise, falls back to legacy in-memory storage.
    """
    from database.connection import get_db as get_db_gen
    
    # If no db provided, get one from the generator
    if db is None:
        try:
            async for db_session in get_db_gen():
                agent = CeliaAgent(db=db_session, user_id=user_id)
                # Copy shared LLM config
                if _shared_llm_config:
                    agent.configure_llm(**_shared_llm_config)
                yield agent
                return
        except Exception as e:
            logger.warning(f"Failed to get db session, using legacy agent: {e}")
            yield _legacy_agent
            return
    
    agent = CeliaAgent(db=db, user_id=user_id)
    # Copy shared LLM config
    if _shared_llm_config:
        agent.configure_llm(**_shared_llm_config)
    yield agent

# Include routers if available
if AUTH_AVAILABLE:
    app.include_router(auth_router)
    app.include_router(admin_router)


# ============= AUTH CONFIGURATION =============

# AUTH_REQUIRED: controls whether authentication is mandatory
# Set to "false" ONLY for development. Default is "true" (mandatory).
AUTH_REQUIRED: bool = os.getenv("AUTH_REQUIRED", "true").lower() == "true"


# ============= AUTH DEPENDENCIES =============

async def require_auth(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Mandatory authentication dependency.
    Rejects requests without valid token with 401 Unauthorized.
    
    Controlled by AUTH_REQUIRED env var:
    - AUTH_REQUIRED=true  (default): Reject requests without valid token
    - AUTH_REQUIRED=false (dev only): Allow all requests (for local dev only)
    """
    # Development bypass (only when AUTH_REQUIRED=false AND no token provided)
    auth_header = request.headers.get("Authorization")
    if not AUTH_REQUIRED and (not auth_header or not auth_header.startswith("Bearer ")):
        return None
    
    # Auth system must be available
    if not AUTH_AVAILABLE:
        raise AuthenticationError("Authentication system is not available")
    
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError("Authentication required. Please provide a valid Bearer token.")
    
    # Extract token
    token = auth_header.split("Bearer ")[1].strip()
    if not token:
        raise AuthenticationError("Authentication token is empty")
    
    # Validate token
    try:
        from auth.auth import decode_token, get_user_by_id
        from database.connection import get_db
        
        payload = decode_token(token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise AuthenticationError("Invalid or expired authentication token")
        
        # Get user from database
        
        user = await get_user_by_id(db, user_id)
            
        if user is None:
            raise AuthenticationError("User not found or inactive")
            
        if not user.is_active:
            raise AuthorizationError("User account is disabled")
            
        return user
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except AuthenticationError:
        # Re-raise AuthenticationError
        raise
    except AuthorizationError:
        # Re-raise AuthorizationError
        raise
    except Exception as e:
        logger.warning(f"Authentication failed: {e}")
        raise AuthenticationError("Invalid or expired authentication token")


# Keep optional_auth for backward compatibility in non-sensitive endpoints
async def optional_auth(request: Request):
    """
    Optional authentication dependency.
    Used for non-sensitive endpoints like /api/health, /api/llm/providers
    """
    if not AUTH_AVAILABLE:
        return None
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    try:
        from auth.auth import decode_token, get_user_by_id
        from database.connection import get_db
        
        token = auth_header.split("Bearer ")[1].strip()
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        user = await get_user_by_id(db, user_id)
        
        if user is None:
            raise AuthenticationError("User not found or inactive")
        
        if not user.is_active:
            raise AuthorizationError("User account is disabled")
        
        return user
    except Exception as e:
        logger.warning(f"Optional auth validation failed: {e}")
        return None


# ============= MIDDLEWARE =============

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Rate limiting and request tracking middleware with structured logging."""
    # Generate request ID
    request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")

    # Bind request context for structured logging
    MonitoringLogger.bind_context(request_id=request_id)

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.is_allowed(client_ip)
    if not allowed:
        MonitoringLogger.clear_context()
        raise RateLimitError(retry_after=retry_after)

    # Request size limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > security_config.max_request_size:
        MonitoringLogger.clear_context()
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "REQUEST_TOO_LARGE", "message": "Request body too large"}}
        )

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Add security headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Structured logging via MonitoringLogger
    if request.url.path.startswith("/api/"):
        MonitoringLogger.log_http_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            client_ip=client_ip,
        )
        # Also keep backward-compatible log
        StructuredLogger.log_event(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )

    # Record Prometheus metrics for API requests
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/metrics"):
        status_bucket = "2xx" if 200 <= response.status_code < 300 else \
                        "4xx" if 400 <= response.status_code < 500 else "5xx"
        PrometheusMetrics.record_error(
            error_type=f"http_{response.status_code}",
            category="http"
        ) if response.status_code >= 400 else None

    # Clear request context
    MonitoringLogger.clear_context()

    return response


# ============= REQUEST MODELS =============

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None
    provider: Optional[str] = None


class LLMConfigRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    hf_token: Optional[str] = None
    primary_provider: str = "gemini"
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    hf_model: str = "meta-llama/Llama-3.3-70B-Instruct"


class ToolExecuteRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


# ============= REST API =============

@app.get("/")
async def root():
    return {
        "name": "celia.pro AI Agent",
        "version": "3.1.0",
        "status": "operational",
        "providers": ["gemini", "groq", "huggingface"],
        "capabilities": [
            "web_search", "code_execution", "file_management",
            "shell_commands", "task_planning", "streaming",
            "gemini_free_tier", "groq_free_tier", "huggingface_free_tier",
            "multi_provider_fallback"
        ]
    }


@app.get("/api/health")
async def health_check():
    """Comprehensive health check with dependency status."""
    llm_status = {}
    if _legacy_agent._llm_client and hasattr(_legacy_agent._llm_client, 'get_status'):
        llm_status = _legacy_agent._llm_client.get_status()

    # Check each component
    components = {
        "api": {"status": "healthy"},
        "tools": {
            "status": "healthy",
            "count": len(_legacy_agent.tool_registry.list_tools()),
        },
        "memory": {"status": "healthy"},
        "llm": {
            "status": "configured" if llm_status else "not_configured",
            **llm_status
        },
        "rate_limiter": {
            "status": "healthy",
            "window": security_config.rate_limit_window,
            "max_requests": security_config.rate_limit_requests,
        },
        "database": {
            "status": "healthy" if db_manager._engine else "not_initialized",
        }
    }

    overall = "healthy" if all(
        c.get("status") in ("healthy", "configured", "not_configured", "not_initialized")
        for c in components.values()
    ) else "degraded"

    return {
        "status": overall,
        "version": "3.2.0",
        "components": components,
        "timestamp": time.time(),
    }


@app.get("/api/ready")
async def readiness_check():
    """Readiness probe for load balancers."""
    return {"ready": True}


@app.get("/api/live")
async def liveness_check():
    """Liveness probe."""
    return {"alive": True}


# ============= LLM ENDPOINTS =============

@app.post("/api/llm/configure")
async def configure_llm(config: LLMConfigRequest, user=Depends(require_auth)):
    """Configure the LLM provider(s) with validation."""
    # Validate API key formats (not values)
    if config.gemini_api_key:
        if not validator.validate_api_key_format(config.gemini_api_key, "gemini"):
            raise NovaMindValidationError(
                message="Gemini API key must start with 'AIza'",
                field="gemini_api_key"
            )

    if config.groq_api_key:
        if not validator.validate_api_key_format(config.groq_api_key, "groq"):
            raise NovaMindValidationError(
                message="Groq API key must start with 'gsk_'",
                field="groq_api_key"
            )

    if config.hf_token:
        if not validator.validate_api_key_format(config.hf_token, "huggingface"):
            raise NovaMindValidationError(
                message="HuggingFace token must start with 'hf_'",
                field="hf_token"
            )

    if config.primary_provider not in ("gemini", "groq", "huggingface"):
        raise NovaMindValidationError(
            message="Provider must be 'gemini', 'groq', or 'huggingface'",
            field="primary_provider"
        )

    status = _legacy_agent.configure_llm(
        gemini_key=config.gemini_api_key,
        groq_key=config.groq_api_key,
        hf_token=config.hf_token,
        primary=config.primary_provider,
        gemini_model=config.gemini_model,
        groq_model=config.groq_model,
        hf_model=config.hf_model
    )

    # Save to shared config so new agents get this config
    global _shared_llm_config
    _shared_llm_config = {
        "gemini_key": config.gemini_api_key,
        "groq_key": config.groq_api_key,
        "hf_token": config.hf_token,
        "primary": config.primary_provider,
        "gemini_model": config.gemini_model,
        "groq_model": config.groq_model,
        "hf_model": config.hf_model,
    }

    # Log without keys
    StructuredLogger.log_event(
        "llm.configured",
        primary=config.primary_provider,
        gemini_configured=bool(config.gemini_api_key),
        groq_configured=bool(config.groq_api_key),
        hf_configured=bool(config.hf_token),
    )

    return {
        "status": "configured",
        "providers": status
    }


@app.get("/api/llm/status")
async def get_llm_status():
    """Get current LLM configuration status (no secrets exposed)."""
    if _shared_llm_config:
        return {
            "configured": True,
            "primary": _shared_llm_config.get("primary"),
            "gemini_configured": bool(_shared_llm_config.get("gemini_key")),
            "groq_configured": bool(_shared_llm_config.get("groq_key")),
            "huggingface_configured": bool(_shared_llm_config.get("hf_token")),
        }
    return {
        "configured": False,
        "message": "No LLM provider configured. Use POST /api/llm/configure"
    }


@app.get("/api/llm/providers")
async def get_llm_providers():
    """Get available LLM providers and models."""
    from core.llm_clients import GroqClient
    return {
        "providers": [
            {
                "id": "gemini",
                "name": "Google Gemini",
                "description": "Free tier - 15 requests/min, 1M tokens/min",
                "models": GeminiClient.SUPPORTED_MODELS,
                "requires": "GEMINI_API_KEY",
                "link": "https://aistudio.google.com/app/apikey"
            },
            {
                "id": "groq",
                "name": "Groq (Ultra-fast LPU)",
                "description": "Free tier - 30 requests/min, 1000 requests/day, ultra-fast inference",
                "models": GroqClient.SUPPORTED_MODELS,
                "requires": "GROQ_API_KEY",
                "link": "https://console.groq.com/keys"
            },
            {
                "id": "huggingface",
                "name": "HuggingFace Inference",
                "description": "Free tier - Rate limited, various open models",
                "models": HuggingFaceClient.FREE_MODELS,
                "requires": "HF_TOKEN",
                "link": "https://huggingface.co/settings/tokens"
            }
        ]
    }


# ============= CHAT ENDPOINT =============

@app.post("/api/chat")
async def chat(request: ChatRequest, user=Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """Send a message to the agent and get a response."""
    try:
        # Validate input
        validated_message = validator.validate_message(request.message)
        
        # Create agent with user context and db session
        user_id = user.id if user else "anonymous"
        agent = CeliaAgent(db=db, user_id=user_id)
        
        # Copy shared LLM config if exists
        if _shared_llm_config:
            agent.configure_llm(**_shared_llm_config)

        response = await agent.process_message(
            validated_message,
            request.conversation_id
        )

        return {
            "response": response.content,
            "conversation_id": agent.current_conversation,
            "steps": [s.dict() for s in response.steps],
            "tool_calls": [tc.dict() for tc in response.tool_calls],
            "execution_time": response.execution_time
        }
    except ValidationError as e:
        raise NovaMindValidationError(message=str(e), field="message")
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=sanitize_error_for_client(e)
        )


# ============= CONVERSATION ENDPOINTS =============

@app.post("/api/conversations")
async def create_conversation(
    title: str = "New Conversation",
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation in the database."""
    if len(title) > 200:
        title = title[:200]
    
    # Create agent with user context and db session
    user_id = user.id if user else "anonymous"
    agent = CeliaAgent(db=db, user_id=user_id)
    
    # Copy shared LLM config if exists
    if _shared_llm_config:
        agent.configure_llm(**_shared_llm_config)
    
    conv_id = await agent.create_conversation(title)
    return {"conversation_id": conv_id, "title": title}


@app.get("/api/conversations")
async def list_conversations(user=Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """List all conversations for the authenticated user."""
    user_id = user.id if user else "anonymous"
    agent = CeliaAgent(db=db, user_id=user_id)
    
    if _shared_llm_config:
        agent.configure_llm(**_shared_llm_config)
    
    conversations = await agent.list_conversations()
    return {"conversations": conversations}


@app.get("/api/conversations/{conv_id}/history")
async def get_conversation_history(conv_id: str, user=Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """Get conversation history from database."""
    user_id = user.id if user else "anonymous"
    agent = CeliaAgent(db=db, user_id=user_id)
    
    if _shared_llm_config:
        agent.configure_llm(**_shared_llm_config)
    
    history = await agent.get_conversation_history(conv_id)
    if not history:
        raise NotFoundError("Conversation")
    return {"messages": history}


# ============= TOOL ENDPOINTS =============

@app.get("/api/tools")
async def list_tools():
    """List all available tools."""
    tools = _legacy_agent.tool_registry.list_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": t.parameters,
                "risk_level": getattr(t, 'risk_level', 'medium').value if hasattr(getattr(t, 'risk_level', None), 'value') else 'medium',
            }
            for t in tools
        ]
    }


@app.post("/api/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, request: ToolExecuteRequest, user=Depends(require_auth)):
    """Execute a tool directly with security checks."""
    # Input validation based on tool
    if tool_name == "execute_code" and "code" in request.arguments:
        try:
            request.arguments["code"] = validator.validate_code(
                request.arguments["code"],
                request.arguments.get("language", "python")
            )
        except ValidationError as e:
            raise NovaMindValidationError(message=str(e), field="code")

    elif tool_name == "shell" and "command" in request.arguments:
        try:
            request.arguments["command"] = validator.validate_shell_command(
                request.arguments["command"]
            )
        except ValidationError as e:
            raise NovaMindValidationError(message=str(e), field="command")

    elif tool_name == "file_manager" and "path" in request.arguments:
        try:
            validator.validate_path(request.arguments["path"])
        except ValidationError as e:
            raise NovaMindValidationError(message=str(e), field="path")

    result = await _legacy_agent.tool_registry.execute(tool_name, **request.arguments)
    return {"tool": tool_name, "result": result}


# ============= MEMORY ENDPOINTS (ADVANCED) =============

def generate_embedding(text: str, dimensions: int = 256) -> List[float]:
    """
    Generate embedding vector for text.
    
    ⚠️ CURRENT IMPLEMENTATION: Hash-based (deterministic)
    - Fast and deterministic
    - No external dependencies
    - Low memory footprint
    - NO SEMANTIC UNDERSTANDING
    
    🎯 PRODUCTION RECOMMENDATION: Use sentence-transformers
    - Install: pip install sentence-transformers
    - Model: all-MiniLM-L6-v2 (80MB, multilingual)
    - Provides true semantic search
    - See: EMBEDDINGS_STRATEGY.md for details
    
    TODO: Replace with sentence-transformers in production
    
    Args:
        text: Input text to embed
        dimensions: Vector dimensions (default: 256)
    
    Returns:
        Normalized vector (List[float])
    
    Example:
        >>> vector = generate_embedding("Hello world")
        >>> len(vector)
        256
    """
    import hashlib
    import numpy as np
    
    # Create deterministic seed from text
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
    np.random.seed(seed)
    
    # Generate normalized vector
    vector = np.random.randn(dimensions).astype(float)
    vector = vector / np.linalg.norm(vector)  # Normalize
    
    return vector.tolist()


class MemoryStoreRequest(BaseModel):
    """Request model for storing advanced memory"""
    key: str = Field(..., min_length=1, max_length=255)
    value: Any
    type: str = Field(default="fact", pattern="^(fact|lesson|preference|context)$")
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: float = Field(default=1.0, ge=0.0, le=1.0)
    ttl_seconds: Optional[int] = None
    generate_vector: bool = True


class MemorySearchRequest(BaseModel):
    """Request model for searching memories"""
    query: Optional[str] = None
    key: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    type: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)
    use_vector_search: bool = True


@app.get("/api/memory")
async def get_memory_summary():
    """Get memory system summary."""
    return _legacy_agent.long_memory.get_summary()


@app.post("/api/memory/store")
async def store_memory(
    request: MemoryStoreRequest,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Store a memory with advanced features (vectors, metadata, TTL)."""
    from database.repositories import MemoryRepository
    
    user_id = user.id if user else "anonymous"
    
    # Prepare metadata
    metadata = {
        "category": request.category or "general",
        "tags": request.tags or [],
        "importance": request.importance
    }
    
    # Generate vector if requested
    vector_256 = None
    if request.generate_vector:
        # Convert value to string for embedding
        value_str = str(request.value) if not isinstance(request.value, str) else request.value
        vector_256 = generate_embedding(value_str, dimensions=256)
    
    # Store in database
    mem_repo = MemoryRepository(db)
    memory = await mem_repo.store_memory(
        user_id=user_id,
        key=request.key,
        value=request.value,
        type=request.type,
        metadata=metadata,
        vector_256=vector_256,
        ttl_seconds=request.ttl_seconds
    )
    
    await db.commit()
    
    return {
        "status": "stored",
        "memory_id": memory.id,
        "key": memory.key,
        "type": memory.type,
        "has_vector": vector_256 is not None,
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None
    }


@app.get("/api/memory/search")
async def search_memory(
    query: Optional[str] = None,
    key: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[str] = None,  # Comma-separated
    type: Optional[str] = None,
    limit: int = 10,
    use_vector_search: bool = True,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Search memories with multiple strategies."""
    from database.repositories import MemoryRepository
    
    user_id = user.id if user else "anonymous"
    mem_repo = MemoryRepository(db)
    
    results = []
    
    # Strategy 1: Exact key lookup
    if key:
        memory = await mem_repo.retrieve_memory(user_id, key)
        if memory:
            results.append({
                "id": memory.id,
                "key": memory.key,
                "value": memory.value,
                "type": memory.type,
                "metadata": memory.memory_metadata,
                "score": 1.0,
                "search_method": "exact_key"
            })
    
    # Strategy 2: Vector similarity search
    elif query and use_vector_search:
        query_vector = generate_embedding(query, dimensions=256)
        memories = await mem_repo.search_by_vector(user_id, query_vector, limit=limit)
        
        for memory in memories:
            # Calculate similarity score (simplified)
            results.append({
                "id": memory.id,
                "key": memory.key,
                "value": memory.value,
                "type": memory.type,
                "metadata": memory.memory_metadata,
                "score": 0.0,  # Could calculate actual cosine similarity
                "search_method": "vector_similarity"
            })
    
    # Strategy 3: Metadata-based search
    elif category or tags or type:
        tag_list = tags.split(",") if tags else None
        memories = await mem_repo.search_by_metadata(
            user_id,
            category=category,
            tags=tag_list,
            type=type,
            limit=limit
        )
        
        for memory in memories:
            results.append({
                "id": memory.id,
                "key": memory.key,
                "value": memory.value,
                "type": memory.type,
                "metadata": memory.memory_metadata,
                "score": 1.0,
                "search_method": "metadata_filter"
            })
    
    await db.commit()
    
    return {
        "results": results[:limit],
        "count": len(results),
        "search_strategy": "vector_similarity" if query and use_vector_search else "metadata_filter" if category or tags else "exact_key"
    }


@app.get("/api/memory/{key}")
async def get_memory(
    key: str,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a specific memory by key."""
    from database.repositories import MemoryRepository
    
    user_id = user.id if user else "anonymous"
    mem_repo = MemoryRepository(db)
    
    memory = await mem_repo.retrieve_memory(user_id, key)
    
    if not memory:
        raise NotFoundError("Memory")
    
    await db.commit()
    
    return {
        "id": memory.id,
        "key": memory.key,
        "value": memory.value,
        "type": memory.type,
        "metadata": memory.memory_metadata,
        "state": memory.state,
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat()
    }


@app.delete("/api/memory/{key}")
async def delete_memory(
    key: str,
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific memory by key."""
    from database.repositories import MemoryRepository
    
    user_id = user.id if user else "anonymous"
    mem_repo = MemoryRepository(db)
    
    deleted = await mem_repo.delete_memory(user_id, key)
    
    if not deleted:
        raise NotFoundError("Memory")
    
    await db.commit()
    
    return {"status": "deleted", "key": key}


@app.post("/api/memory/cleanup")
async def cleanup_expired_memories(
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Clean up expired memories."""
    from database.repositories import MemoryRepository
    
    mem_repo = MemoryRepository(db)
    count = await mem_repo.cleanup_expired()
    
    await db.commit()
    
    return {"status": "cleaned", "deleted_count": count}


# ============= REFLECTION ENDPOINTS =============

@app.get("/api/reflection/stats")
async def get_reflection_stats():
    """Get reflection system statistics."""
    return _legacy_agent.reflection.get_reflection_summary()


@app.get("/api/reflection/memories")
async def get_reflection_memories():
    """Get reflection memories for learning."""
    return {"memories": _legacy_agent.reflection.export_memories()}


# ============= SYSTEM ENDPOINTS =============

@app.get("/api/system/metrics")
async def get_metrics(db: Optional[AsyncSession] = Depends(get_db)):
    """
    Get comprehensive system metrics for monitoring dashboards.
    
    Returns:
        System statistics including:
        - Cost tracking summary
        - Tool audit summary
        - Rate limiter usage
        - Database statistics (user count, conversation count, etc.)
        - Application info
    """
    # Gather database statistics
    db_stats = {}
    if db is not None:
        try:
            from sqlalchemy import text, select, func
            from database.models import User, Conversation, Message, MemoryItem

            # Count users
            user_count_result = await db.execute(select(func.count(User.id)))
            user_count = user_count_result.scalar() or 0

            # Count active users (logged in within last 24 hours)
            try:
                from datetime import datetime, timedelta
                active_since = datetime.utcnow() - timedelta(hours=24)
                active_count_result = await db.execute(
                    select(func.count(User.id)).where(User.last_login >= active_since)
                )
                active_user_count = active_count_result.scalar() or 0
            except Exception:
                active_user_count = 0

            # Count conversations
            conv_count_result = await db.execute(select(func.count(Conversation.id)))
            conversation_count = conv_count_result.scalar() or 0

            # Count messages
            msg_count_result = await db.execute(select(func.count(Message.id)))
            message_count = msg_count_result.scalar() or 0

            # Count memory items
            mem_count_result = await db.execute(select(func.count(MemoryItem.id)))
            memory_count = mem_count_result.scalar() or 0

            db_stats = {
                "total_users": user_count,
                "active_users_24h": active_user_count,
                "total_conversations": conversation_count,
                "total_messages": message_count,
                "total_memory_items": memory_count,
            }

            # Update Prometheus gauges
            PrometheusMetrics.set_active_users(active_user_count)

        except Exception as e:
            db_stats = {"error": f"Failed to gather DB stats: {str(e)}"}
    else:
        db_stats = {"status": "database_not_available"}

    import time as _time

    return {
        "cost_tracking": cost_tracker.get_summary(),
        "tool_audit": policy_engine.get_audit_summary(),
        "rate_limiter": rate_limiter.get_usage("default"),
        "database": db_stats,
        "application": {
            "version": "3.2.0",
            "uptime_seconds": _time.time() - _app_start_time,
            "llm_configured": bool(_shared_llm_config),
            "auth_required": AUTH_REQUIRED,
        },
    }


# ============= WEBSOCKET =============

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    active_connections[client_id] = websocket
    logger.info(f"WebSocket connected: {client_id}")

    await websocket.send_json({
        "type": "connected",
        "client_id": client_id,
        "message": "Welcome to celia.pro! Send a message to start."
    })

    try:
        while True:
            data = await websocket.receive_text()

            # Size limit
            if len(data) > security_config.max_request_size:
                await websocket.send_json({
                    "type": "error",
                    "message": "Message too large"
                })
                continue

            message = json.loads(data)

            if message.get("type") == "chat":
                content = message.get("content", "")
                try:
                    content = validator.validate_message(content)
                except ValidationError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
                    continue

                await websocket.send_json({
                    "type": "processing",
                    "message": "Analyzing your request..."
                })

                # Create agent for this WebSocket session
                ws_agent = CeliaAgent()
                if _shared_llm_config:
                    ws_agent.configure_llm(**_shared_llm_config)

                async for chunk in ws_agent.stream_response(content):
                    await websocket.send_json(chunk)

                response = await ws_agent.process_message(content)
                await websocket.send_json({
                    "type": "response",
                    "content": response.content,
                    "conversation_id": ws_agent.current_conversation,
                    "tool_calls": [tc.dict() for tc in response.tool_calls],
                    "execution_time": response.execution_time
                })

            elif message.get("type") == "config_llm":
                config = message.get("config", {})
                _legacy_agent.configure_llm(**config)
                _shared_llm_config.update(config)
                await websocket.send_json({
                    "type": "llm_configured",
                    "status": _shared_llm_config
                })

            elif message.get("type") == "cancel":
                # Cancel any processing in active connections
                await websocket.send_json({
                    "type": "cancelled",
                    "message": "Processing cancelled"
                })

    except WebSocketDisconnect:
        del active_connections[client_id]
        logger.info(f"WebSocket disconnected: {client_id}")
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if client_id in active_connections:
            del active_connections[client_id]


# ============= STATIC FILES =============

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
