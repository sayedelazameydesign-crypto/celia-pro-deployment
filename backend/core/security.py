"""
celia.pro Security Layer
=========================
Input validation, CORS hardening, rate limiting, request sanitization.
"""

import time
import re
import os
import hashlib
import uuid
import logging
from typing import Dict, Optional, Any, List
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============= SECURITY CONFIGURATION =============

@dataclass
class SecurityConfig:
    """Security configuration - loaded from environment."""
    cors_origins: List[str] = field(default_factory=lambda: [
        # Development
        "http://localhost:5173",
        "http://localhost:5174",
    ] + ([
        # Production (from environment variable)
        *os.getenv("CORS_ORIGINS", "").split(",")
    ] if os.getenv("CORS_ORIGINS") else []))
    max_request_size: int = 1_000_000  # 1MB
    max_message_length: int = 10_000
    max_code_length: int = 50_000
    rate_limit_requests: int = 30
    rate_limit_window: int = 60  # seconds
    allowed_shell_commands: List[str] = field(default_factory=lambda: [
        "ls", "cat", "head", "tail", "wc", "grep", "find", "echo",
        "pwd", "whoami", "date", "uname", "df", "du", "free", "uptime",
        "python3", "python", "node", "npm", "pip", "git", "curl", "wget",
        "mkdir", "touch", "cp", "mv", "env", "which", "type", "file"
    ])
    blocked_shell_patterns: List[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/", r"mkfs", r"dd\s+if=", r":\(\)\{.*\|.*&\}",
        r"chmod\s+-R\s+777\s+/", r"sudo\s+rm", r">\s*/dev/sd",
        r"curl.*\|\s*sh", r"wget.*\|\s*bash", r"eval\s*\(",
        r"exec\s*\(", r"__import__\s*\(\s*['\"]os['\"]",
        r"subprocess\s*\.\s*call", r"os\.system\s*\("
    ])
    blocked_code_patterns: List[str] = field(default_factory=lambda: [
        r"__import__\s*\(\s*['\"]os['\"]",
        r"__import__\s*\(\s*['\"]subprocess['\"]",
        r"os\.system\s*\(",
        r"os\.popen\s*\(",
        r"subprocess\.(call|run|Popen|check_output)\s*\(",
        r"exec\s*\(\s*compile\s*\(",
        r"__class__\s*\.\s*__bases__",
        r"__subclasses__\s*\(\s*\)",
        r"__mro__",
        r"globals\s*\(\s*\)\s*\[",
        r"getattr\s*\(\s*__builtins__",
    ])


# ============= RATE LIMITER =============

class RateLimiter:
    """Token-bucket rate limiter per client identifier."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, client_id: str) -> tuple:
        """Check if request is allowed. Returns (allowed: bool, retry_after: int)."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > window_start
        ]

        if len(self._requests[client_id]) >= self.max_requests:
            oldest = self._requests[client_id][0]
            retry_after = int(oldest + self.window_seconds - now) + 1
            return False, max(retry_after, 1)

        self._requests[client_id].append(now)
        return True, 0

    def get_usage(self, client_id: str) -> Dict:
        """Get current usage for a client."""
        now = time.time()
        window_start = now - self.window_seconds
        active = [t for t in self._requests.get(client_id, []) if t > window_start]
        return {
            "used": len(active),
            "limit": self.max_requests,
            "window_seconds": self.window_seconds,
            "remaining": self.max_requests - len(active)
        }


# ============= INPUT VALIDATOR =============

class ValidationError(Exception):
    """Raised when input validation fails."""
    def __init__(self, field: str, message: str, code: str = "VALIDATION_ERROR"):
        self.field = field
        self.code = code
        super().__init__(f"[{field}] {message}")


class InputValidator:
    """Validates and sanitizes all user input."""

    def __init__(self, config: SecurityConfig):
        self.config = config

    def validate_message(self, message: str) -> str:
        """Validate and sanitize a chat message."""
        if not message or not isinstance(message, str):
            raise ValidationError("message", "Message is required and must be a string")

        message = message.strip()
        if len(message) == 0:
            raise ValidationError("message", "Message cannot be empty")

        if len(message) > self.config.max_message_length:
            raise ValidationError(
                "message",
                f"Message exceeds maximum length of {self.config.max_message_length} characters"
            )

        # Strip null bytes and control characters (except newline/tab)
        message = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)
        return message

    def validate_code(self, code: str, language: str = "python") -> str:
        """Validate code input and check for dangerous patterns."""
        if not code or not isinstance(code, str):
            raise ValidationError("code", "Code is required and must be a string")

        if len(code) > self.config.max_code_length:
            raise ValidationError(
                "code",
                f"Code exceeds maximum length of {self.config.max_code_length} characters"
            )

        # Check for dangerous patterns
        for pattern in self.config.blocked_code_patterns:
            if re.search(pattern, code):
                raise ValidationError(
                    "code",
                    f"Code contains disallowed pattern. Remove system-level operations.",
                    code="CODE_SAFETY_VIOLATION"
                )

        return code

    def validate_shell_command(self, command: str) -> str:
        """Validate shell command for safety."""
        if not command or not isinstance(command, str):
            raise ValidationError("command", "Command is required")

        command = command.strip()
        if len(command) > 5000:
            raise ValidationError("command", "Command too long (max 5000 chars)")

        # Check blocked patterns
        for pattern in self.config.blocked_shell_patterns:
            if re.search(pattern, command):
                raise ValidationError(
                    "command",
                    "Command contains disallowed operation",
                    code="COMMAND_SAFETY_VIOLATION"
                )

        return command

    def validate_path(self, path: str, workspace_root: str = "/home/user") -> str:
        """Validate file path to prevent path traversal."""
        if not path or not isinstance(path, str):
            raise ValidationError("path", "Path is required")

        # Resolve the path
        import os
        resolved = os.path.realpath(os.path.join(workspace_root, path))

        # Must be within workspace
        workspace_real = os.path.realpath(workspace_root)
        if not resolved.startswith(workspace_real):
            raise ValidationError(
                "path",
                "Path traversal detected: path must be within workspace",
                code="PATH_TRAVERSAL_BLOCKED"
            )

        return resolved

    def validate_api_key_format(self, key: str, provider: str) -> bool:
        """Basic format validation for API keys (not security check)."""
        if not key or not isinstance(key, str):
            return False
        if len(key) < 10 or len(key) > 500:
            return False
        if provider == "gemini" and not key.startswith("AIza"):
            return False
        if provider == "groq" and not key.startswith("gsk_"):
            return False
        if provider == "huggingface" and not key.startswith("hf_"):
            return False
        return True


# ============= REQUEST TRACKING =============

@dataclass
class RequestContext:
    """Context for a single request - used for tracing and auditing."""
    request_id: str
    session_id: Optional[str] = None
    client_ip: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[float] = None
    status: Optional[str] = None
    tool_calls: int = 0
    tokens_used: int = 0

    @staticmethod
    def create(session_id: Optional[str] = None, client_ip: Optional[str] = None) -> 'RequestContext':
        return RequestContext(
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            client_ip=client_ip,
        )


# ============= PROMPT INJECTION DETECTION =============

class PromptInjectionDetector:
    """Basic detection of prompt injection attempts in tool outputs."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above)\s+instructions",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"new\s+instructions?\s*:",
        r"system\s*:\s*",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"\[INST\]",
        r"\[\/INST\]",
        r"###\s*(system|instruction)",
        r"act\s+as\s+(if\s+)?(a\s+)?",
        r"forget\s+(everything|all|your)\s+",
        r"override\s+(previous|all|safety)",
        r"disregard\s+(all\s+)?(previous|safety|rules)",
    ]

    @classmethod
    def detect(cls, text: str) -> tuple:
        """Check text for injection patterns. Returns (is_suspicious: bool, patterns_found: list)."""
        if not text:
            return False, []

        found = []
        text_lower = text.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower):
                found.append(pattern)

        return len(found) > 0, found

    @classmethod
    def sanitize_tool_output(cls, text: str, max_length: int = 10000) -> str:
        """Sanitize tool output before sending to LLM."""
        if not text:
            return ""

        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + "\n[... truncated]"

        # Add boundary markers to prevent injection
        text = f"[TOOL OUTPUT START]\n{text}\n[TOOL OUTPUT END]"
        return text


# ============= MASKING =============

def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Mask a secret for display: shows only last N chars."""
    if not secret or len(secret) <= visible_chars + 2:
        return "•" * 8
    return "•" * (len(secret) - visible_chars) + secret[-visible_chars:]


def sanitize_error_for_client(error: Exception) -> Dict[str, Any]:
    """Create a safe error response that doesn't leak internals."""
    error_msg = str(error)

    # Classify error
    if isinstance(error, ValidationError):
        return {
            "error": {
                "code": error.code,
                "message": error_msg,
                "field": error.field if hasattr(error, 'field') else None,
                "retryable": False,
            }
        }

    # Don't leak stack traces or internals
    if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
        return {
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "A service is temporarily unavailable. Please try again.",
                "retryable": True,
            }
        }

    if "rate" in error_msg.lower():
        return {
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests. Please wait a moment.",
                "retryable": True,
            }
        }

    return {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again.",
            "retryable": True,
        }
    }
