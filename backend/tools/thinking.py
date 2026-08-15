"""
NovaMind Thinking Tool
=======================
Internal reasoning and planning tool for the agent.
"""

from .base import BaseTool
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ThinkingTool(BaseTool):
    """Internal thinking/reasoning tool for the agent."""

    name = "think"
    description = "Use this tool for internal reasoning, planning, analysis, and decision-making. Use it to think through complex problems step by step, plan multi-step tasks, or analyze information before taking action."
    category = "reasoning"
    parameters = {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "Your detailed reasoning, analysis, or plan"
            },
            "type": {
                "type": "string",
                "enum": ["reasoning", "planning", "analysis", "reflection", "critique"],
                "description": "Type of thinking to perform",
                "default": "reasoning"
            }
        },
        "required": ["thought"]
    }

    async def execute(self, thought: str, type: str = "reasoning", **kwargs) -> str:
        """Process thinking."""
        prefixes = {
            "reasoning": "🧠 Reasoning",
            "planning": "📋 Planning",
            "analysis": "🔍 Analysis",
            "reflection": "💭 Reflection",
            "critique": "⚡ Critique",
        }
        prefix = prefixes.get(type, "🧠 Thinking")
        return f"{prefix}:\n{thought}\n\n[Thought recorded. Proceed with your plan.]"
