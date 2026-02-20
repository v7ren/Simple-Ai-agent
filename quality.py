"""Quality and safety checks."""

from typing import Optional
from dataclasses import dataclass
import re

from config import Settings


@dataclass
class QualityResult:
    """Result of quality check."""
    passed: bool
    needs_fix: bool
    reason: str = ""


class QualityChecker:
    """Check quality and safety of final answer."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def check(self, content: str) -> QualityResult:
        """Check content for quality and safety issues."""
        
        if not content:
            return QualityResult(
                passed=False,
                needs_fix=True,
                reason="Empty response",
            )
        
        # Policy check
        if self._has_disallowed_content(content):
            return QualityResult(
                passed=False,
                needs_fix=True,
                reason="Content may contain disallowed information",
            )
        
        # Check for obvious hallucination markers
        if self._has_hallucination_markers(content):
            return QualityResult(
                passed=False,
                needs_fix=True,
                reason="Response contains potential hallucination markers",
            )
        
        # Check formatting
        if not self._has_valid_markdown(content):
            return QualityResult(
                passed=False,
                needs_fix=False,  # Don't fix, just note
                reason="Markdown formatting issues detected",
            )
        
        return QualityResult(passed=True, needs_fix=False)
    
    def _has_disallowed_content(self, content: str) -> bool:
        """Check for disallowed content."""
        content_lower = content.lower()
        
        disallowed = [
            "i cannot help with",
            "i can't help with",
        ]
        
        # If response contains refusal language but is trying to continue, flag it
        for phrase in disallowed:
            if phrase in content_lower:
                # Check if there's substantive content after
                idx = content_lower.index(phrase)
                if len(content) - idx < 50:
                    return True
        
        return False
    
    def _has_hallucination_markers(self, content: str) -> bool:
        """Check for potential hallucination markers."""
        markers = [
            r'\b(?:I|we) think\b',
            r'\b(?:I|we) believe\b',
            r'\b(?:I|we) assume\b',
            r'\b(?:probably|likely|maybe)\b',
        ]
        
        count = 0
        for marker in markers:
            if re.search(marker, content, re.IGNORECASE):
                count += 1
        
        # If too many uncertainty markers
        return count > 3
    
    def _has_valid_markdown(self, content: str) -> bool:
        """Check for basic markdown validity."""
        # Simple check for unbalanced code blocks
        code_blocks = content.count("```")
        if code_blocks % 2 != 0:
            return False
        
        return True
