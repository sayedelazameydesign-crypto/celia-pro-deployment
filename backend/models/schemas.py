"""
NovaMind Data Models
====================
Pydantic models for the agent system.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime
import uuid


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCall(BaseModel):
    """Represents a tool invocation."""
    id: str = Field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:8]}")
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    status: ToolStatus = ToolStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Step(BaseModel):
    """A single step in the agent's execution plan."""
    id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    description: str
    thought: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    output: Optional[str] = None


class Message(BaseModel):
    """A message in the conversation."""
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    role: MessageRole
    content: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    step: Optional[Step] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    """A full conversation session."""
    id: str = Field(default_factory=lambda: f"conv_{uuid.uuid4().hex[:8]}")
    title: str = "New Conversation"
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentConfig(BaseModel):
    """Configuration for the agent."""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_steps: int = 20
    system_prompt: str = ""
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class AgentResponse(BaseModel):
    """Response from the agent."""
    content: str
    steps: List[Step] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    total_tokens: Optional[int] = None
    execution_time: Optional[float] = None


class ToolDefinition(BaseModel):
    """Definition of a tool available to the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]
    category: str = "general"
    is_enabled: bool = True
