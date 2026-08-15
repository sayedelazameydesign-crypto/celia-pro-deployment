"""
celia.pro Tool System
======================
Base class and registry for tools with security enforcement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import time
import logging
import sys
import os

from core.tool_security import policy_engine, RiskLevel, ToolAuditEntry

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all celia.pro tools."""

    name: str = "base_tool"
    description: str = "Base tool - should be overridden"
    parameters: Dict[str, Any] = {}
    category: str = "general"
    risk_level: RiskLevel = RiskLevel.MEDIUM

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute the tool with the given arguments."""
        pass

    def validate_params(self, **kwargs) -> bool:
        """Validate the input parameters."""
        return True

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert tool to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def __repr__(self):
        return f"<Tool: {self.name} ({self.category}, risk={self.risk_level.value})>"


class ToolRegistry:
    """Registry for managing available tools with security enforcement."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a new tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str):
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None):
        """List all registered tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def get_openai_tools(self) -> list:
        """Get all tools in OpenAI format."""
        return [t.to_openai_format() for t in self._tools.values()]

    def get_anthropic_tools(self) -> list:
        """Get all tools in Anthropic format."""
        return [t.to_anthropic_format() for t in self._tools.values()]

    async def execute(self, name: str, request_id: str = "unknown", **kwargs) -> str:
        """Execute a tool with security checks and audit logging."""
        tool = self.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        # Security policy check
        allowed, reason = policy_engine.check_permission(name, kwargs, request_id)
        if not allowed:
            logger.warning(f"Tool execution blocked: {name} - {reason}")
            return f"Error: Tool execution blocked by security policy: {reason}"

        # Execute with timeout and audit
        start_time = time.time()
        try:
            result = await tool.execute(**kwargs)
            duration_ms = (time.time() - start_time) * 1000

            # Audit log
            entry = ToolAuditEntry(
                request_id=request_id,
                tool_name=name,
                risk_level=policy_engine.get_risk_level(name).value,
                arguments_summary=self._sanitize_args(kwargs),
                status="success",
                duration_ms=duration_ms,
                timestamp=time.time(),
            )
            policy_engine.log_execution(entry)

            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            entry = ToolAuditEntry(
                request_id=request_id,
                tool_name=name,
                risk_level=policy_engine.get_risk_level(name).value,
                arguments_summary=self._sanitize_args(kwargs),
                status="error",
                duration_ms=duration_ms,
                timestamp=time.time(),
                error=str(e),
            )
            policy_engine.log_execution(entry)
            logger.error(f"Tool execution error ({name}): {e}")
            return f"Error executing {name}: {str(e)}"

    @staticmethod
    def _sanitize_args(args: Dict) -> str:
        """Create a safe summary of tool arguments (no secrets)."""
        safe = {}
        for key, value in args.items():
            str_val = str(value)
            if len(str_val) > 200:
                str_val = str_val[:200] + "..."
            safe[key] = str_val
        try:
            return json.dumps(safe, ensure_ascii=False)
        except Exception:
            return "[unserializable]"
