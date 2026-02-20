"""Semantic retrieval engine."""

from typing import List, Optional, Dict, Any
from context.ltm import MemoryEntry, LongTermMemoryStore


class RetrievalEngine:
    """Retrieval engine for semantic and keyword search."""
    
    def __init__(self, ltm_store: LongTermMemoryStore):
        self.ltm_store = ltm_store
    
    def search(
        self,
        session_id: str,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
        min_importance: float = 0.0,
    ) -> List[MemoryEntry]:
        """Search memories for relevant context."""
        
        # Get memories from LTM
        memories = self.ltm_store.retrieve(
            session_id=session_id,
            query=query,
            category=category,
            limit=top_k * 2,  # Get more for filtering
        )
        
        # Score and filter memories
        scored = []
        for memory in memories:
            if memory.importance >= min_importance:
                score = self._score_relevance(memory, query)
                scored.append((score, memory))
        
        # Sort by score and return top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:top_k]]
    
    def _score_relevance(self, memory: MemoryEntry, query: str) -> float:
        """Score memory relevance to query."""
        import re
        
        query_lower = query.lower()
        content_lower = memory.content.lower()
        
        # Exact match bonus
        if query_lower in content_lower:
            base_score = 1.0
        else:
            # Keyword overlap
            query_words = set(re.findall(r'\b\w+\b', query_lower))
            content_words = set(re.findall(r'\b\w+\b', content_lower))
            overlap = len(query_words & content_words)
            base_score = overlap / max(len(query_words), 1)
        
        # Importance weighting
        weighted_score = base_score * 0.7 + memory.importance * 0.3
        
        return weighted_score
    
    def format_for_context(self, memories: List[MemoryEntry]) -> str:
        """Format retrieved memories for context."""
        if not memories:
            return ""
        
        parts = ["Relevant context from memory:"]
        for i, mem in enumerate(memories, 1):
            parts.append(f"{i}. [{mem.category}] {mem.content}")
        
        return "\n".join(parts)
