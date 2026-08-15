"""
NovaMind Task Planner
======================
Breaks down complex tasks into executable steps.
"""

from typing import List, Dict, Any, Optional
import sys, os

from models.schemas import Step, TaskStatus
import logging
import json

logger = logging.getLogger(__name__)


PLANNING_PROMPT = """You are NovaMind's task planning module. Given a user request, break it down into concrete, executable steps.

Each step should:
1. Be specific and actionable
2. Specify which tool to use (if any)
3. Include the expected output
4. Be ordered logically

Available tools:
- web_search: Search the web for information
- execute_code: Run Python/JavaScript/Bash code
- file_manager: Read/write/manage files
- shell: Execute shell commands
- think: Internal reasoning and analysis

Respond with a JSON array of steps in this format:
[
  {
    "description": "What this step does",
    "tool": "tool_name or null for thinking-only steps",
    "arguments": {"param": "value"},
    "depends_on": [] // indices of steps this depends on
  }
]
"""


class TaskPlanner:
    """Plans and decomposes complex tasks into steps."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.max_steps = 20

    async def plan(self, task: str, context: Optional[Dict] = None) -> List[Step]:
        """Create an execution plan for a task."""
        if self.llm_client:
            return await self._llm_plan(task, context)
        return self._heuristic_plan(task)

    async def _llm_plan(self, task: str, context: Optional[Dict] = None) -> List[Step]:
        """Use LLM to create a plan."""
        messages = [
            {"role": "system", "content": PLANNING_PROMPT},
            {"role": "user", "content": f"Create a plan for: {task}"}
        ]
        if context:
            messages.append({"role": "user", "content": f"Context: {json.dumps(context)}"})

        try:
            response = await self.llm_client.chat(messages, temperature=0.3)
            plan_data = json.loads(response)
            steps = []
            for item in plan_data:
                steps.append(Step(
                    description=item.get("description", ""),
                    thought=json.dumps(item.get("arguments", {})),
                ))
            return steps[:self.max_steps]
        except Exception as e:
            logger.warning(f"LLM planning failed, falling back to heuristic: {e}")
            return self._heuristic_plan(task)

    def _heuristic_plan(self, task: str) -> List[Step]:
        """Create a plan using heuristic rules."""
        task_lower = task.lower()
        steps = []

        # Detect task type and create appropriate steps
        if any(w in task_lower for w in ["research", "find", "search", "look up", "what is"]):
            steps = [
                Step(description=f"Analyze the query: '{task}'"),
                Step(description=f"Search the web for relevant information about '{task}'"),
                Step(description="Compile and summarize the findings"),
            ]
        elif any(w in task_lower for w in ["code", "program", "script", "function", "build", "create app"]):
            steps = [
                Step(description=f"Analyze requirements: '{task}'"),
                Step(description="Design the solution architecture"),
                Step(description="Write the code implementation"),
                Step(description="Test and validate the code"),
            ]
        elif any(w in task_lower for w in ["write", "article", "essay", "report", "document"]):
            steps = [
                Step(description=f"Research topic: '{task}'"),
                Step(description="Outline the document structure"),
                Step(description="Write the content"),
                Step(description="Review and format the document"),
            ]
        elif any(w in task_lower for w in ["analyze", "compare", "evaluate"]):
            steps = [
                Step(description=f"Define analysis criteria for: '{task}'"),
                Step(description="Gather relevant data"),
                Step(description="Perform analysis"),
                Step(description="Present findings and conclusions"),
            ]
        else:
            # Generic plan
            steps = [
                Step(description=f"Understand the task: '{task}'"),
                Step(description="Determine the best approach"),
                Step(description="Execute the solution"),
                Step(description="Verify the results"),
            ]

        return steps[:self.max_steps]

    async def replan(self, original_plan: List[Step], failed_step: int, error: str) -> List[Step]:
        """Adjust the plan based on a failure."""
        # Keep steps before the failure, replace the rest
        remaining = [s for i, s in enumerate(original_plan) if i < failed_step]
        remaining.append(Step(
            description=f"Recover from error in step {failed_step}: {error}",
            thought="Need to find an alternative approach",
        ))
        remaining.append(Step(
            description="Complete the remaining tasks",
        ))
        return remaining
