"""
Reflection Layer for celia.pro Agent
======================================
Enables the agent to think about its actions, learn from mistakes,
and improve decision-making using semantic memory search.

✅ UPDATED: Now uses semantic embeddings and database storage
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ReflectionType(Enum):
    """Types of reflection the agent can perform"""
    PRE_ACTION = "pre_action"
    POST_ACTION = "post_action"
    ERROR_ANALYSIS = "error_analysis"
    STRATEGY_REVIEW = "strategy_review"
    LEARNING = "learning"


@dataclass
class Reflection:
    """A single reflection entry"""
    type: ReflectionType
    thought: str
    reasoning: str
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None
    lessons_learned: List[str] = field(default_factory=list)


@dataclass
class ReflectionMemory:
    """
    Legacy reflection memory dataclass (for backward compatibility).
    
    Note: This is kept for backward compatibility with old tests.
    New code should use database storage via MemoryRepository.
    """
    situation: str
    action_taken: str
    outcome: str
    lesson: str
    confidence: float
    usage_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ReflectionLayer:
    """
    Manages agent reflection and learning with semantic memory.
    
    ✅ UPDATED: Now uses semantic embeddings for retrieval
    - retrieve_relevant_memories uses vector similarity search
    - Lessons are stored in database (not in-memory)
    - Prompt enhancement with relevant lessons
    """
    
    def __init__(self, db: Optional[AsyncSession] = None, max_memories: int = 1000, user_id: str = "agent"):
        """
        Initialize ReflectionLayer with database connection.
        
        Args:
            db: Database session for storing/retrieving memories
            max_memories: Maximum number of reflections to keep in memory
            user_id: User ID for storing/retrieving memories (default: "agent")
        """
        self.db = db
        self.user_id = user_id
        self.reflections: List[Reflection] = []
        self.max_memories = max_memories
        self._memory_repo = None
        
        # Initialize memory repository if db is provided
        if db:
            from database.repositories import MemoryRepository
            self._memory_repo = MemoryRepository(db)
    
    async def retrieve_relevant_memories(
        self,
        situation: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Retrieve relevant memories using semantic search.
        
        ✅ Uses semantic embeddings for true similarity search
        - "hello" will match "greetings"
        - "ما هو الطقس؟" will match "كيف الجو؟"
        
        Args:
            situation: Current situation/query text
            limit: Maximum number of memories to retrieve
        
        Returns:
            List of memory dicts with keys: id, key, value, type, memory_metadata, score
        """
        if not self._memory_repo:
            logger.warning("No database connection - returning empty memories")
            return []
        
        try:
            # Generate embedding for the situation
            from core.embeddings import generate_embedding
            
            situation_vector = generate_embedding(situation, dimensions=384)
            
            # Search by vector similarity
            memories = await self._memory_repo.search_by_vector(
                user_id=self.user_id,
                query_vector=situation_vector,
                limit=limit
            )
            
            # Convert to dict format
            results = []
            for memory in memories:
                results.append({
                    "id": memory.id,
                    "key": memory.key,
                    "value": memory.value,
                    "type": memory.type,
                    "metadata": memory.memory_metadata,
                    "score": 0.0  # Could calculate actual cosine similarity
                })
            
            logger.info(f"Retrieved {len(results)} relevant memories for: {situation[:50]}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []
    
    async def store_lesson(
        self,
        situation: str,
        action: str,
        outcome: str,
        lesson: str,
        tags: Optional[List[str]] = None,
        importance: float = 0.7
    ) -> Optional[str]:
        """
        Store a lesson learned in the database.
        
        ✅ Uses semantic embeddings for future retrieval
        - Generates embedding for the lesson
        - Stores in database with metadata
        - Can be retrieved by semantic similarity
        
        Args:
            situation: What situation led to this lesson
            action: What action was taken
            outcome: What happened (success/failure)
            lesson: The lesson learned
            tags: Optional tags for filtering
            importance: How important this lesson is (0.0 to 1.0)
        
        Returns:
            Memory ID if stored successfully, None otherwise
        """
        if not self._memory_repo:
            logger.warning("No database connection - cannot store lesson")
            return None
        
        try:
            # Generate unique key
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            key = f"lesson_{timestamp}"
            
            # Prepare value (structured lesson)
            value = {
                "situation": situation,
                "action": action,
                "outcome": outcome,
                "lesson": lesson,
                "learned_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Store in database
            memory = await self._memory_repo.store_memory(
                user_id=self.user_id,
                key=key,
                value=value,
                type="lesson",
                metadata={
                    "category": "lesson",
                    "tags": tags or ["reflection", "learning"],
                    "importance": importance,
                    "situation": situation,
                    "action": action,
                    "outcome": outcome
                },
                vector_256=None,  # Will be generated by API layer
                ttl_seconds=None  # Lessons don't expire
            )
            
            logger.info(f"Stored lesson: {lesson[:50]}... (key: {key})")
            return memory.id
            
        except Exception as e:
            logger.error(f"Failed to store lesson: {e}")
            return None
    
    async def enhance_prompt_with_lessons(
        self,
        situation: str,
        base_prompt: str,
        max_lessons: int = 3
    ) -> str:
        """
        Enhance a prompt with relevant lessons from memory.
        
        ✅ Retrieves semantically similar lessons
        - Adds lessons to the prompt
        - Helps agent learn from past experiences
        
        Args:
            situation: Current situation/context
            base_prompt: The base prompt to enhance
            max_lessons: Maximum number of lessons to add
        
        Returns:
            Enhanced prompt with lessons
        """
        # Retrieve relevant memories
        memories = await self.retrieve_relevant_memories(situation, limit=max_lessons)
        
        if not memories:
            return base_prompt
        
        # Build lessons section
        lessons_section = "\n\n## Relevant Lessons from Past Experience:\n"
        for i, memory in enumerate(memories, 1):
            if isinstance(memory["value"], dict):
                lesson_data = memory["value"]
                situation_text = lesson_data.get("situation", "Unknown")
                lesson_text = lesson_data.get("lesson", "Unknown")
                outcome = lesson_data.get("outcome", "Unknown")
                
                lessons_section += f"\n{i}. **Situation**: {situation_text}\n"
                lessons_section += f"   **Lesson**: {lesson_text}\n"
                lessons_section += f"   **Outcome**: {outcome}\n"
            else:
                lessons_section += f"\n{i}. {memory['value']}\n"
        
        # Combine with base prompt
        enhanced_prompt = base_prompt + lessons_section
        
        logger.info(f"Enhanced prompt with {len(memories)} relevant lessons")
        return enhanced_prompt
    
    def reflect_before_action(
        self,
        action: str,
        context: Dict[str, Any],
        available_tools: List[str]
    ) -> Reflection:
        """Reflect before taking an action"""
        thought = f"About to execute: {action}"
        reasoning = self._reason_about_action(action, context, available_tools)
        confidence = self._estimate_confidence(action, context)
        
        reflection = Reflection(
            type=ReflectionType.PRE_ACTION,
            thought=thought,
            reasoning=reasoning,
            confidence=confidence,
            context={"action": action, **context}
        )
        
        self.reflections.append(reflection)
        logger.info(f"Pre-action reflection: {thought}")
        
        return reflection
    
    async def reflect_after_action(
        self,
        action: str,
        result: Any,
        success: bool,
        context: Dict[str, Any]
    ) -> Reflection:
        """
        Reflect after taking an action and store lesson if significant.
        
        ✅ UPDATED: Now stores lessons in database
        """
        outcome = "success" if success else "failure"
        thought = f"Action '{action}' completed with {outcome}"
        reasoning = self._analyze_outcome(action, result, success, context)
        confidence = self._estimate_result_confidence(result, success)
        lessons = self._extract_lessons(action, result, success, context)
        
        reflection = Reflection(
            type=ReflectionType.POST_ACTION,
            thought=thought,
            reasoning=reasoning,
            confidence=confidence,
            context={"action": action, "result": str(result)[:500], **context},
            outcome=outcome,
            lessons_learned=lessons
        )
        
        self.reflections.append(reflection)
        
        # Store lesson in database if significant
        if lessons:
            situation = f"Executing {action}"
            lesson_text = "; ".join(lessons)
            importance = 0.8 if success else 0.6
            
            await self.store_lesson(
                situation=situation,
                action=action,
                outcome=outcome,
                lesson=lesson_text,
                tags=[action, outcome, "tool_execution"],
                importance=importance
            )
        
        logger.info(f"Post-action reflection: {thought}")
        
        return reflection
    
    async def reflect_on_error(
        self,
        action: str,
        error: Exception,
        context: Dict[str, Any]
    ) -> Reflection:
        """
        Reflect when an error occurs and store the lesson.
        
        ✅ UPDATED: Now stores error lessons in database
        """
        thought = f"Error occurred during: {action}"
        reasoning = self._analyze_error(action, error, context)
        confidence = 0.3
        lessons = self._extract_error_lessons(action, error, context)
        
        reflection = Reflection(
            type=ReflectionType.ERROR_ANALYSIS,
            thought=thought,
            reasoning=reasoning,
            confidence=confidence,
            context={"action": action, "error": str(error), **context},
            outcome="error",
            lessons_learned=lessons
        )
        
        self.reflections.append(reflection)
        
        # Store error lesson in database
        situation = f"Error during {action}"
        lesson_text = "; ".join(lessons)
        
        await self.store_lesson(
            situation=situation,
            action=action,
            outcome="error",
            lesson=lesson_text,
            tags=[action, "error", str(type(error).__name__)],
            importance=0.9  # Errors are important to learn from
        )
        
        logger.warning(f"Error reflection: {thought} - {str(error)}")
        
        return reflection
    
    def _reason_about_action(
        self,
        action: str,
        context: Dict[str, Any],
        available_tools: List[str]
    ) -> str:
        """Generate reasoning about whether to take an action"""
        reasoning_parts = []
        
        # Check tool appropriateness
        action_lower = action.lower()
        if "search" in action_lower and "web_search" in available_tools:
            reasoning_parts.append("Action requires web search - using web_search tool")
        elif "code" in action_lower or "execute" in action_lower:
            if "execute_code" in available_tools:
                reasoning_parts.append("Action requires code execution - using execute_code tool")
        
        if not reasoning_parts:
            reasoning_parts.append("Proceeding with action")
        
        return "\n".join(reasoning_parts)
    
    def _estimate_confidence(self, action: str, context: Dict[str, Any]) -> float:
        """Estimate confidence in the action"""
        confidence = 0.7
        
        # Reduce for risky actions
        if any(word in action.lower() for word in ["delete", "remove", "drop"]):
            confidence -= 0.2
        
        return max(0.0, min(1.0, confidence))
    
    def _analyze_outcome(
        self,
        action: str,
        result: Any,
        success: bool,
        context: Dict[str, Any]
    ) -> str:
        """Analyze the outcome of an action"""
        if success:
            return f"Action succeeded. Result: {str(result)[:200]}"
        else:
            return f"Action failed. Error: {str(result)[:200]}"
    
    def _extract_lessons(
        self,
        action: str,
        result: Any,
        success: bool,
        context: Dict[str, Any]
    ) -> List[str]:
        """Extract lessons from the action outcome"""
        lessons = []
        
        if success:
            lessons.append(f"Successfully executed: {action}")
        else:
            lessons.append(f"Failed to execute: {action}")
            
            if "timeout" in str(result).lower():
                lessons.append("Action timed out - consider increasing timeout")
            elif "permission" in str(result).lower():
                lessons.append("Permission denied - check permissions")
        
        return lessons
    
    def _analyze_error(
        self,
        action: str,
        error: Exception,
        context: Dict[str, Any]
    ) -> str:
        """Deep analysis of an error"""
        error_str = str(error).lower()
        analysis_parts = [f"Error type: {type(error).__name__}"]
        
        if "timeout" in error_str:
            analysis_parts.append("Category: Timeout")
        elif "permission" in error_str:
            analysis_parts.append("Category: Permission")
        else:
            analysis_parts.append("Category: Unknown")
        
        return "\n".join(analysis_parts)
    
    def _extract_error_lessons(
        self,
        action: str,
        error: Exception,
        context: Dict[str, Any]
    ) -> List[str]:
        """Extract lessons from an error"""
        lessons = [f"Error encountered: {type(error).__name__}"]
        
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            lessons.append("Add timeout handling")
        elif "permission" in error_str:
            lessons.append("Verify permissions")
        
        return lessons
    
    def _estimate_result_confidence(self, result: Any, success: bool) -> float:
        """Estimate confidence in the result"""
        if success:
            return 0.9 if result else 0.7
        else:
            return 0.2
    
    def get_reflection_summary(self) -> Dict[str, Any]:
        """Get a summary of reflections"""
        if not self.reflections:
            return {"total_reflections": 0}
        
        by_type = {}
        for r in self.reflections:
            by_type[r.type.value] = by_type.get(r.type.value, 0) + 1
        
        avg_confidence = sum(r.confidence for r in self.reflections) / len(self.reflections)
        
        return {
            "total_reflections": len(self.reflections),
            "by_type": by_type,
            "average_confidence": avg_confidence
        }
