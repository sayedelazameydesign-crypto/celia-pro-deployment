"""
celia.pro Tool Security
========================
Risk levels, permission checks, and safe tool execution.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Tool risk classification."""
    READ_ONLY = "read_only"       # No side effects (search, read file)
    LOW = "low"                   # Minor side effects (think, list)
    MEDIUM = "medium"             # Moderate side effects (write file)
    HIGH = "high"                 # Significant side effects (execute code)
    DESTRUCTIVE = "destructive"   # Irreversible (delete, rm)


@dataclass
class ToolPolicy:
    """Security policy for a tool."""
    risk_level: RiskLevel
    timeout_seconds: int = 30
    max_output_size: int = 50_000
    requires_confirmation: bool = False
    allowed_paths: Optional[List[str]] = None  # For file tools
    blocked_patterns: Optional[List[str]] = None  # For code/shell tools
    audit_log: bool = True


# Default policies for built-in tools
DEFAULT_TOOL_POLICIES: Dict[str, ToolPolicy] = {
    "web_search": ToolPolicy(
        risk_level=RiskLevel.LOW,
        timeout_seconds=15,
    ),
    "execute_code": ToolPolicy(
        risk_level=RiskLevel.HIGH,
        timeout_seconds=30,
        blocked_patterns=[
            r"os\.system", r"subprocess", r"__import__\s*\(\s*['\"]os",
            r"__import__\s*\(\s*['\"]subprocess",
        ],
    ),
    "file_manager": ToolPolicy(
        risk_level=RiskLevel.MEDIUM,
        timeout_seconds=10,
    ),
    "shell": ToolPolicy(
        risk_level=RiskLevel.HIGH,
        timeout_seconds=30,
        blocked_patterns=[
            r"rm\s+-rf\s+/", r"mkfs", r"dd\s+if=",
            r"chmod\s+-R\s+777", r"sudo",
        ],
    ),
    "think": ToolPolicy(
        risk_level=RiskLevel.READ_ONLY,
        timeout_seconds=5,
    ),
}


@dataclass
class ToolAuditEntry:
    """Audit log entry for tool execution."""
    request_id: str
    tool_name: str
    risk_level: str
    arguments_summary: str  # Sanitized, no secrets
    status: str  # "allowed", "blocked", "error", "timeout"
    duration_ms: float
    timestamp: float
    error: Optional[str] = None


class ToolPolicyEngine:
    """Enforces security policies for tool execution."""

    def __init__(self):
        self.policies = dict(DEFAULT_TOOL_POLICIES)
        self.audit_log: List[ToolAuditEntry] = []
        self._max_audit_entries = 1000

    def register_policy(self, tool_name: str, policy: ToolPolicy):
        """Register or update a tool's security policy."""
        self.policies[tool_name] = policy

    def check_permission(self, tool_name: str, arguments: Dict[str, Any],
                        request_id: str = "unknown") -> tuple:
        """
        Check if a tool execution is allowed.
        Returns (allowed: bool, reason: Optional[str])
        """
        policy = self.policies.get(tool_name)
        if not policy:
            # Unknown tools default to MEDIUM risk
            logger.warning(f"No policy for tool '{tool_name}', using default MEDIUM risk")
            return True, None

        # Check blocked patterns in arguments
        if policy.blocked_patterns:
            import re
            args_str = str(arguments)
            for pattern in policy.blocked_patterns:
                if re.search(pattern, args_str):
                    self._log_audit(request_id, tool_name, policy, "blocked",
                                   0, error=f"Blocked pattern: {pattern}")
                    return False, f"Tool arguments contain disallowed pattern"

        return True, None

    def get_timeout(self, tool_name: str) -> int:
        """Get the timeout for a tool."""
        policy = self.policies.get(tool_name)
        return policy.timeout_seconds if policy else 30

    def get_risk_level(self, tool_name: str) -> RiskLevel:
        """Get the risk level of a tool."""
        policy = self.policies.get(tool_name)
        return policy.risk_level if policy else RiskLevel.MEDIUM

    def log_execution(self, entry: ToolAuditEntry):
        """Add an audit entry."""
        self.audit_log.append(entry)
        if len(self.audit_log) > self._max_audit_entries:
            self.audit_log = self.audit_log[-self._max_audit_entries:]

    def _log_audit(self, request_id: str, tool_name: str, policy: ToolPolicy,
                  status: str, duration_ms: float, error: Optional[str] = None):
        """Internal audit logging."""
        entry = ToolAuditEntry(
            request_id=request_id,
            tool_name=tool_name,
            risk_level=policy.risk_level.value,
            arguments_summary="[see audit]",
            status=status,
            duration_ms=duration_ms,
            timestamp=time.time(),
            error=error,
        )
        self.log_execution(entry)

    def get_audit_summary(self) -> Dict:
        """Get audit summary."""
        total = len(self.audit_log)
        blocked = sum(1 for e in self.audit_log if e.status == "blocked")
        errors = sum(1 for e in self.audit_log if e.status == "error")
        return {
            "total_executions": total,
            "blocked": blocked,
            "errors": errors,
            "recent": [
                {
                    "tool": e.tool_name,
                    "risk": e.risk_level,
                    "status": e.status,
                    "time": e.timestamp,
                }
                for e in self.audit_log[-10:]
            ]
        }


# Global policy engine instance
policy_engine = ToolPolicyEngine()
