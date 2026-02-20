"""Input normalization."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from langdetect import detect, LangDetectException

from context.run_context import RunContext


@dataclass
class NormalizedInput:
    """Normalized input ready for processing."""
    
    content: str
    original: str
    language: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    run_id: str = ""
    session_id: str = ""


class InputNormalizer:
    """Normalizes user input."""
    
    def normalize(
        self,
        message: str,
        run_context: RunContext,
        metadata: Optional[dict[str, Any]] = None,
    ) -> NormalizedInput:
        """Normalize input: trim, detect language, attach metadata."""
        
        # Trim whitespace
        trimmed = message.strip()
        content = " ".join(trimmed.split())  # Normalize whitespace
        
        # Detect language
        try:
            language = detect(content)
        except LangDetectException:
            language = "unknown"
        
        return NormalizedInput(
            content=content,
            original=message,
            language=language,
            metadata=metadata or {},
            run_id=run_context.run_id,
            session_id=run_context.session_id,
        )
