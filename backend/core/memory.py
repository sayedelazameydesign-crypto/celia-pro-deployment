"""
NovaMind Memory System
=======================
Short-term and long-term memory for the agent.
"""

from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime
import json
import logging
import os

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """Conversation context window management."""

    def __init__(self, max_messages: int = 50, max_tokens: int = 128000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.messages: deque = deque(maxlen=max_messages)

    def add(self, message: Dict[str, Any]):
        """Add a message to short-term memory."""
        self.messages.append({
            **message,
            "timestamp": datetime.now().isoformat()
        })
        self._trim_if_needed()

    def get_context(self, last_n: Optional[int] = None) -> List[Dict]:
        """Get conversation context."""
        msgs = list(self.messages)
        if last_n:
            msgs = msgs[-last_n:]
        return msgs

    def clear(self):
        """Clear short-term memory."""
        self.messages.clear()

    def _trim_if_needed(self):
        """Trim messages if exceeding token limit."""
        total = sum(len(json.dumps(m)) for m in self.messages)
        while total > self.max_tokens * 4 and len(self.messages) > 2:
            self.messages.popleft()
            total = sum(len(json.dumps(m)) for m in self.messages)


class LongTermMemory:
    """Persistent memory across conversations."""

    def __init__(self, storage_path: str = "/home/user/novamind/memory"):
        self.storage_path = storage_path
        self.memories: Dict[str, Any] = {}
        self.knowledge_base: List[Dict] = []
        self._load()

    def _load(self):
        """Load memories from disk."""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            path = os.path.join(self.storage_path, "memory.json")
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.memories = data.get("memories", {})
                    self.knowledge_base = data.get("knowledge_base", [])
        except Exception as e:
            logger.warning(f"Failed to load memory: {e}")

    def _save(self):
        """Save memories to disk."""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            path = os.path.join(self.storage_path, "memory.json")
            with open(path, 'w') as f:
                json.dump({
                    "memories": self.memories,
                    "knowledge_base": self.knowledge_base,
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save memory: {e}")

    def store(self, key: str, value: Any, category: str = "general"):
        """Store a memory."""
        self.memories[key] = {
            "value": value,
            "category": category,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._save()

    def recall(self, key: str) -> Optional[Any]:
        """Recall a memory by key."""
        memory = self.memories.get(key)
        if memory:
            return memory.get("value")
        return None

    def search(self, query: str) -> List[Dict]:
        """Search memories by query."""
        results = []
        query_lower = query.lower()
        for key, memory in self.memories.items():
            if query_lower in key.lower() or query_lower in str(memory.get("value", "")).lower():
                results.append({"key": key, **memory})
        return results

    def add_knowledge(self, content: str, source: str = "", tags: List[str] = None):
        """Add to the knowledge base."""
        self.knowledge_base.append({
            "content": content,
            "source": source,
            "tags": tags or [],
            "created_at": datetime.now().isoformat()
        })
        self._save()

    def search_knowledge(self, query: str, limit: int = 5) -> List[Dict]:
        """Search the knowledge base."""
        query_lower = query.lower()
        scored = []
        for item in self.knowledge_base:
            score = 0
            content = item.get("content", "").lower()
            if query_lower in content:
                score += content.count(query_lower)
            for tag in item.get("tags", []):
                if query_lower in tag.lower():
                    score += 2
            if score > 0:
                scored.append((score, item))
        scored.sort(reverse=True)
        return [item for _, item in scored[:limit]]

    def forget(self, key: str) -> bool:
        """Remove a memory."""
        if key in self.memories:
            del self.memories[key]
            self._save()
            return True
        return False

    def get_summary(self) -> Dict:
        """Get a summary of memory state."""
        return {
            "total_memories": len(self.memories),
            "knowledge_items": len(self.knowledge_base),
            "categories": list(set(m.get("category") for m in self.memories.values())),
            "last_updated": datetime.now().isoformat()
        }
