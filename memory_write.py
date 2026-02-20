"""Memory write logic."""

from typing import Optional, List
import re

from context.ltm import LongTermMemoryStore
from config import Settings
from tools.executor import ToolExecutionResult


class MemoryWriter:
    """Decides and executes memory writes."""
    
    def __init__(self, ltm: LongTermMemoryStore, settings: Settings):
        self.ltm = ltm
        self.settings = settings
    
    def should_write(
        self,
        session_id: str,
        tool_name: str,
        result: ToolExecutionResult,
    ) -> bool:
        """Decide if result should be written to LTM."""
        
        if not self.ltm:
            return False
        
        if not self.settings.ltm_enabled:
            return False
        
        # Don't write failed results
        if not result.success:
            return False
        
        # Check for sensitive data
        if self._contains_sensitive_data(result.content):
            return False
        
        # Heuristic: only write substantial results
        if len(result.content) < 20:
            return False
        
        # Check frequency: don't spam writes
        # In production, implement rate limiting here
        
        return True
    
    def write(
        self,
        session_id: str,
        content: str,
        category: str = "fact",
        importance: float = 0.5,
    ) -> Optional[str]:
        """Write to LTM. Returns memory ID if successful."""
        
        if not self.ltm:
            return None
        
        memory_id = self.ltm.store(
            session_id=session_id,
            content=content,
            category=category,
            importance=importance,
        )
        
        return memory_id
    
    def consider_write(
        self,
        session_id: str,
        tool_name: str,
        result: ToolExecutionResult,
    ) -> Optional[str]:
        """Consider and execute memory write."""
        
        if not self.should_write(session_id, tool_name, result):
            return None
        
        # Simple heuristic-based categorization
        if "preference" in result.content.lower():
            category = "preference"
            importance = 0.8
        elif "error" in result.content.lower() or "failed" in result.content.lower():
            category = "outcome"
            importance = 0.3
        else:
            category = "fact"
            importance = 0.5
        
        # Extract a summary
        summary = self._extract_summary(result.content)
        
        return self.write(
            session_id=session_id,
            content=summary,
            category=category,
            importance=importance,
        )
    
    def _contains_sensitive_data(self, text: str) -> bool:
        """Check if text contains sensitive data."""
        text_lower = text.lower()
        
        sensitive_patterns = [
            r'password',
            r'secret',
            r'token',
            r'api[_-]?key',
            r'private[_-]?key',
            r'ssn',
            r'social[_-]?security',
            r'credit[_-]?card',
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _extract_summary(self, content: str, max_length: int = 500) -> str:
        """Extract a summary from content."""
        # Simple truncation
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."
