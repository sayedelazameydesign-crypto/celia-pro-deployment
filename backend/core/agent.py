"""
celia.pro AI Agent
==================
The main agent loop that orchestrates planning, tool use, and response generation.
Integrated with PostgreSQL for persistent storage.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from datetime import datetime, timezone
import json
import time
import logging
import os

import sys, os

from core.planner import TaskPlanner
from core.memory import ShortTermMemory, LongTermMemory
from core.llm_clients import LLMRouter, GeminiClient, HuggingFaceClient
from core.reflection import ReflectionLayer
from models.schemas import (
    Message, MessageRole, Step, ToolCall, ToolStatus, TaskStatus,
    Conversation, AgentConfig, AgentResponse
)
from tools.base import ToolRegistry
from tools.web_search import WebSearchTool
from tools.code_executor import CodeExecutorTool
from tools.file_manager import FileManagerTool
from tools.shell import ShellTool
from tools.thinking import ThinkingTool
from database.repositories import (
    ConversationRepository,
    MessageRepository
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Celia, an advanced AI agent system powered by celia.pro built for 2026. You are a multi-tool AI assistant capable of:

1. **Web Search** - Finding current information from the web
2. **Code Execution** - Running Python, JavaScript, and Bash code
3. **File Management** - Reading, writing, and managing files
4. **Shell Commands** - Executing system commands
5. **Deep Thinking** - Reasoning through complex problems step by step

## Your Behavior:
- You break down complex tasks into manageable steps
- You think before acting, using the think tool for reasoning
- You use tools proactively when they help accomplish tasks
- You provide clear, structured responses
- You adapt your approach based on results and errors
- You are transparent about what you're doing and why

## Response Format:
When using tools, explain what you're doing and why. After tool execution, analyze the results and decide next steps. Always aim for the most efficient path to completing the task.

## Constraints:
- Never execute harmful or destructive commands
- Always validate inputs before execution
- Respect user privacy and data security
- Be honest about limitations

Current date: {date}
Available tools: {tools}
"""


class CeliaAgent:
    """The main AI agent that orchestrates all components with database integration."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        db: Optional[AsyncSession] = None,
        user_id: Optional[str] = None
    ):
        self.config = config or AgentConfig()
        self.tool_registry = ToolRegistry()
        self.planner = TaskPlanner()
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        
        # Database integration
        self.db = db
        self.user_id = user_id
        self.current_conversation: Optional[str] = None
        self.is_processing = False
        self._llm_client = None
        
        # Initialize ReflectionLayer with database connection
        self.reflection = ReflectionLayer(db=db, user_id=user_id or "agent")
        
        # Repositories (only if db is provided)
        self.conv_repo: Optional[ConversationRepository] = None
        self.msg_repo: Optional[MessageRepository] = None
        
        if self.db:
            self.conv_repo = ConversationRepository(self.db)
            self.msg_repo = MessageRepository(self.db)

        # Register default tools
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all default tools."""
        self.tool_registry.register(WebSearchTool())
        self.tool_registry.register(CodeExecutorTool())
        self.tool_registry.register(FileManagerTool())
        self.tool_registry.register(ShellTool())
        self.tool_registry.register(ThinkingTool())

    def set_llm_client(self, client):
        """Set the LLM client for the agent."""
        self._llm_client = client
        self.planner.llm_client = client

    def configure_llm(self, gemini_key: Optional[str] = None, groq_key: Optional[str] = None,
                     hf_token: Optional[str] = None, primary: str = "gemini",
                     gemini_model: str = "gemini-2.0-flash",
                     groq_model: str = "llama-3.3-70b-versatile",
                     hf_model: str = "meta-llama/Llama-3.3-70B-Instruct"):
        """Configure LLM with Gemini, Groq, and/or HuggingFace."""
        router = LLMRouter(
            gemini_key=gemini_key,
            groq_key=groq_key,
            hf_token=hf_token,
            primary=primary,
            gemini_model=gemini_model,
            groq_model=groq_model,
            hf_model=hf_model
        )
        self._llm_client = router
        self.planner.llm_client = router
        return router.get_status()

    def _get_system_prompt(self) -> str:
        """Generate the system prompt."""
        tools = [t.name for t in self.tool_registry.list_tools()]
        return SYSTEM_PROMPT.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            tools=", ".join(tools)
        )
    
    def _format_memories_for_prompt(self, memories: List[Dict]) -> str:
        """
        Format retrieved memories for inclusion in the prompt.
        
        Args:
            memories: List of memory dicts from retrieve_relevant_memories
        
        Returns:
            Formatted string with lessons from past experiences
        """
        if not memories:
            return ""
        
        sections = ["\n## Relevant Lessons from Past Experience:\n"]
        
        for i, memory in enumerate(memories, 1):
            value = memory.get("value", {})
            if isinstance(value, dict):
                situation = value.get("situation", "Unknown situation")
                lesson = value.get("lesson", "Unknown lesson")
                outcome = value.get("outcome", "Unknown outcome")
                
                sections.append(f"\n{i}. **Situation**: {situation}")
                sections.append(f"   **Lesson**: {lesson}")
                sections.append(f"   **Outcome**: {outcome}")
            else:
                sections.append(f"\n{i}. {value}")
        
        sections.append("\nUse these lessons to inform your decision-making.\n")
        
        return "\n".join(sections)

    async def create_conversation(self, title: str = "New Conversation") -> str:
        """Create a new conversation and return its ID.
        
        If database is available, persists to database.
        Otherwise, uses in-memory storage (backward compatibility).
        """
        if self.db and self.conv_repo:
            # Database-backed conversation
            from database.models import Conversation as DBConversation
            conv = DBConversation(
                user_id=self.user_id,
                title=title
            )
            await self.conv_repo.create(conv)
            
            # Add system message to database
            if self.msg_repo:
                await self.msg_repo.add_message(
                    conversation_id=conv.id,
                    role="system",
                    content=self._get_system_prompt()
                )
            
            self.current_conversation = conv.id
            return conv.id
        else:
            # Fallback to in-memory (backward compatibility)
            from models.schemas import Conversation as SchemaConversation
            conv = SchemaConversation(title=title)
            
            # Add system message
            system_msg = Message(
                role=MessageRole.SYSTEM,
                content=self._get_system_prompt()
            )
            conv.messages.append(system_msg)
            
            # Store in legacy dict (only for backward compatibility)
            if not hasattr(self, '_legacy_conversations'):
                self._legacy_conversations = {}
            self._legacy_conversations[conv.id] = conv
            
            self.current_conversation = conv.id
            return conv.id

    async def process_message(self, user_input: str, conversation_id: Optional[str] = None) -> AgentResponse:
        """Process a user message and generate a response with safety limits."""
        from core.agent_safety import AgentBudget, AgentLimits, AgentLimitExceeded
        
        start_time = time.time()

        # Initialize agent budget for safety limits
        budget = AgentBudget(limits=AgentLimits())

        # Set up conversation
        if conversation_id:
            self.current_conversation = conversation_id
        elif not self.current_conversation:
            await self.create_conversation()

        conv_id = self.current_conversation
        self.is_processing = True

        # Add user message to database
        if self.db and self.msg_repo:
            await self.msg_repo.add_message(
                conversation_id=conv_id,
                role="user",
                content=user_input
            )
        else:
            # Legacy in-memory
            if hasattr(self, '_legacy_conversations') and conv_id in self._legacy_conversations:
                conv = self._legacy_conversations[conv_id]
                user_msg = Message(role=MessageRole.USER, content=user_input)
                conv.messages.append(user_msg)

        self.short_memory.add({"role": "user", "content": user_input})

        try:
            # Step 0: Retrieve relevant lessons from memory (if db is available)
            enhanced_context = ""
            if self.db and self.reflection._memory_repo:
                try:
                    relevant_memories = await self.reflection.retrieve_relevant_memories(
                        situation=user_input,
                        limit=3
                    )
                    if relevant_memories:
                        enhanced_context = self._format_memories_for_prompt(relevant_memories)
                        logger.info(f"Retrieved {len(relevant_memories)} relevant memories")
                except Exception as e:
                    logger.warning(f"Failed to retrieve memories: {e}")

            # Step 1: Plan the task
            steps = await self.planner.plan(user_input)

            # Step 2: Execute the plan
            all_tool_calls = []
            response_parts = []

            if self._llm_client:
                # Use LLM-powered agent loop with safety budget and enhanced context
                result = await self._llm_agent_loop(user_input, steps, budget, enhanced_context)
            else:
                # Use demo mode
                result = await self._demo_agent_loop(user_input, steps)

            all_tool_calls = result.get("tool_calls", [])
            response_content = result.get("content", "")
            response_steps = result.get("steps", steps)

            # Add assistant response to database
            import json
            from datetime import datetime as dt, timezone as tz
            
            def json_serial(obj):
                """JSON serializer for objects not serializable by default"""
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif hasattr(obj, 'value'):  # Enum
                    return obj.value
                elif isinstance(obj, dict):
                    return {k: json_serial(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [json_serial(i) for i in obj]
                elif isinstance(obj, (int, float, str, bool, type(None))):
                    return obj
                else:
                    return str(obj)
            
            # Serialize tool_calls properly
            tool_calls_data = None
            if all_tool_calls:
                tool_calls_data = []
                for tc in all_tool_calls:
                    tc_dict = tc.model_dump() if hasattr(tc, 'model_dump') else tc.dict()
                    tc_json = json.dumps(tc_dict, default=json_serial)
                    tool_calls_data.append(json.loads(tc_json))
            
            # Serialize steps properly
            steps_data = None
            if response_steps:
                steps_data = []
                for s in response_steps:
                    step_dict = s.model_dump() if hasattr(s, 'model_dump') else s.dict()
                    step_json = json.dumps(step_dict, default=json_serial)
                    step_data = json.loads(step_json)
                    steps_data.append(step_data)
            
            if self.db and self.msg_repo:
                await self.msg_repo.add_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=response_content,
                    tool_calls=tool_calls_data,
                    steps=steps_data
                )
            else:
                # Legacy in-memory
                if hasattr(self, '_legacy_conversations') and conv_id in self._legacy_conversations:
                    conv = self._legacy_conversations[conv_id]
                    assistant_msg = Message(
                        role=MessageRole.ASSISTANT,
                        content=response_content,
                        tool_calls=all_tool_calls
                    )
                    conv.messages.append(assistant_msg)

            self.short_memory.add({"role": "assistant", "content": response_content})

            execution_time = time.time() - start_time

            return AgentResponse(
                content=response_content,
                steps=response_steps,
                tool_calls=all_tool_calls,
                execution_time=execution_time
            )

        except AgentLimitExceeded as e:
            # Agent exceeded safety limits
            logger.warning(f"Agent safety limit exceeded: {e}")
            error_msg = f"I've reached a safety limit while processing your request: {str(e)}. Let me try a simpler approach."
            return AgentResponse(
                content=error_msg,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            logger.error(f"Agent error: {e}")
            error_msg = f"I encountered an error while processing your request: {str(e)}. Let me try a different approach."
            return AgentResponse(
                content=error_msg,
                execution_time=time.time() - start_time
            )
        finally:
            self.is_processing = False

    async def _llm_agent_loop(self, user_input: str, steps: List[Step], budget=None, enhanced_context: str = "") -> Dict:
        """
        LLM-powered agent loop with function calling, safety limits, and reflection.
        
        ✅ UPDATED: Now uses enhanced_context from reflection layer
        """
        from core.agent_safety import AgentBudget, AgentLimits
        
        # Initialize budget if not provided
        if budget is None:
            budget = AgentBudget(limits=AgentLimits())
        
        # Build system prompt with enhanced context (lessons from memory)
        base_prompt = self._get_system_prompt()
        system_prompt = base_prompt + enhanced_context if enhanced_context else base_prompt
        
        messages = [
            {"role": "system", "content": system_prompt},
            *self.short_memory.get_context()
        ]

        all_tool_calls = []
        all_steps = []

        for iteration in range(self.config.max_steps):
            # Check safety limits
            budget.check_iteration()
            budget.check_runtime()

            # Call LLM with tools
            response = await self._llm_client.chat_with_tools(
                messages=messages,
                tools=self.tool_registry.get_openai_tools(),
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            # Check if LLM wants to use tools
            if response.get("tool_calls"):
                step = Step(
                    description=f"Executing tools (iteration {iteration + 1})",
                    status=TaskStatus.EXECUTING
                )

                for tc in response["tool_calls"]:
                    # Check tool call limit
                    budget.check_tool_call()
                    
                    tool_call = ToolCall(
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"]),
                        status=ToolStatus.RUNNING,
                    )

                    # Pre-action reflection
                    self.reflection.reflect_before_action(
                        action=tool_call.name,
                        context=tool_call.arguments,
                        available_tools=[t.name for t in self.tool_registry.list_tools()]
                    )

                    # Execute tool
                    result = await self.tool_registry.execute(
                        tool_call.name,
                        **tool_call.arguments
                    )
                    tool_call.result = result
                    tool_call.status = ToolStatus.COMPLETED
                    tool_call.completed_at = datetime.now()
                    all_tool_calls.append(tool_call)
                    step.tool_calls.append(tool_call)

                    # Post-action reflection (async to store lesson in DB)
                    await self.reflection.reflect_after_action(
                        action=tool_call.name,
                        result=result,
                        success="error" not in result.lower(),
                        context=tool_call.arguments
                    )

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })

                all_steps.append(step)
            else:
                # LLM generated a final response
                content = response.get("content", "")
                return {
                    "content": content,
                    "tool_calls": all_tool_calls,
                    "steps": all_steps
                }

        return {
            "content": "I've completed my analysis but reached the maximum number of steps. Here's what I found so far based on the tools I've executed.",
            "tool_calls": all_tool_calls,
            "steps": all_steps
        }

    async def _demo_agent_loop(self, user_input: str, steps: List[Step]) -> Dict:
        """Demo agent loop without LLM (for showcasing the system)."""
        all_tool_calls = []
        response_parts = []

        for step in steps:
            step.status = TaskStatus.EXECUTING
            response_parts.append(f"\n### Step: {step.description}")

            # Simulate tool usage based on step description
            tool_name, tool_args = self._infer_tool(step.description)
            if tool_name:
                tool_call = ToolCall(
                    name=tool_name,
                    arguments=tool_args,
                    status=ToolStatus.RUNNING,
                    started_at=datetime.now()
                )

                result = await self.tool_registry.execute(tool_name, **tool_args)
                tool_call.result = result
                tool_call.status = ToolStatus.COMPLETED
                tool_call.completed_at = datetime.now()
                all_tool_calls.append(tool_call)
                step.tool_calls.append(tool_call)

                response_parts.append(f"**Tool**: `{tool_name}`\n")
                if len(result) > 500:
                    response_parts.append(f"**Result**: {result[:500]}...\n")
                else:
                    response_parts.append(f"**Result**: {result}\n")

            step.status = TaskStatus.COMPLETED

        content = "\n".join(response_parts) if response_parts else \
            "I've analyzed your request. In production mode with an LLM API key, I would use advanced reasoning to provide a detailed response with tool calls."

        return {
            "content": content,
            "tool_calls": all_tool_calls,
            "steps": steps
        }

    def _infer_tool(self, step_description: str) -> tuple:
        """Infer which tool to use based on step description."""
        desc = step_description.lower()
        if any(w in desc for w in ["search", "find", "look up", "research"]):
            # Extract query from description
            return "web_search", {"query": step_description, "num_results": 3}
        elif any(w in desc for w in ["code", "execute", "run", "calculate", "script"]):
            return "execute_code", {"code": f"# Auto-generated for: {step_description}\nprint('Processing...')"}
        elif any(w in desc for w in ["file", "write", "save", "read", "create"]):
            return "file_manager", {"action": "list", "path": "."}
        elif any(w in desc for w in ["think", "analyze", "plan", "reason"]):
            return "think", {"thought": step_description, "type": "reasoning"}
        elif any(w in desc for w in ["command", "system", "install", "shell"]):
            return "shell", {"command": f"echo 'Executing: {step_description}'"}
        return None, {}

    async def stream_response(self, user_input: str) -> AsyncGenerator[Dict, None]:
        """Stream the agent's response token by token."""
        # Start processing
        yield {"type": "status", "content": "thinking", "message": "Analyzing your request..."}

        # Plan
        steps = await self.planner.plan(user_input)
        yield {"type": "plan", "steps": [{"description": s.description} for s in steps]}

        # Execute each step
        for i, step in enumerate(steps):
            yield {"type": "step_start", "step": i, "description": step.description}

            tool_name, tool_args = self._infer_tool(step.description)
            if tool_name:
                yield {"type": "tool_start", "tool": tool_name, "arguments": tool_args}
                result = await self.tool_registry.execute(tool_name, **tool_args)
                yield {"type": "tool_result", "tool": tool_name, "result": result}

            yield {"type": "step_complete", "step": i}

        yield {"type": "status", "content": "complete", "message": "Done!"}

    async def get_conversation_history(self, conversation_id: Optional[str] = None) -> List[Dict]:
        """Get conversation history from database or legacy storage."""
        conv_id = conversation_id or self.current_conversation
        
        if self.db and self.msg_repo and conv_id:
            # Database-backed history
            messages = await self.msg_repo.get_conversation_messages(conv_id)
            return [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "tool_calls": msg.tool_calls or []
                }
                for msg in messages
                if msg.role != "system"
            ]
        else:
            # Legacy in-memory
            if hasattr(self, '_legacy_conversations') and conv_id and conv_id in self._legacy_conversations:
                conv = self._legacy_conversations[conv_id]
                return [
                    {
                        "id": msg.id,
                        "role": msg.role.value,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "tool_calls": [tc.dict() for tc in msg.tool_calls] if msg.tool_calls else []
                    }
                    for msg in conv.messages
                    if msg.role != MessageRole.SYSTEM
                ]
        return []

    async def list_conversations(self) -> List[Dict]:
        """List all conversations from database or legacy storage."""
        if self.db and self.conv_repo and self.user_id:
            # Database-backed list
            conversations = await self.conv_repo.get_user_conversations(self.user_id)
            return [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": conv.message_count
                }
                for conv in conversations
            ]
        else:
            # Legacy in-memory
            if hasattr(self, '_legacy_conversations'):
                return [
                    {
                        "id": conv.id,
                        "title": conv.title,
                        "created_at": conv.created_at.isoformat(),
                        "updated_at": conv.updated_at.isoformat(),
                        "message_count": len(conv.messages)
                    }
                    for conv in self._legacy_conversations.values()
                ]
        return []
