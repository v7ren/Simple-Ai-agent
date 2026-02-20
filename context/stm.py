"""Short-term memory."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from collections import deque
import threading


@dataclass
class MemoryMessage:
    """A message in short-term memory."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class ShortTermMemory:
    """Short-term memory for recent conversation turns."""
    
    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._sessions: dict[str, deque] = {}
        self._lock = threading.Lock()
    
    def _get_session(self, session_id: str) -> deque:
        """Get or create session memory."""
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self.max_turns)
        return self._sessions[session_id]
    
    def append(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Add a message to STM."""
        with self._lock:
            session = self._get_session(session_id)
            message = MemoryMessage(
                role=role,
                content=content,
                metadata=metadata or {},
            )
            session.append(message)
    
    def get_recent(
        self,
        session_id: str,
        n: Optional[int] = None,
    ) -> List[MemoryMessage]:
        """Get recent messages from STM."""
        with self._lock:
            session = self._get_session(session_id)
            messages = list(session)
            if n is not None:
                messages = messages[-n:]
            return messages
    
    def get_all(self, session_id: str) -> List[MemoryMessage]:
        """Get all messages in session."""
        return self.get_recent(session_id, n=None)
    
    def clear(self, session_id: str) -> None:
        """Clear session memory."""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].clear()
    
    def to_messages(self, session_id: str) -> List[dict]:
        """Convert STM to OpenAI-style message format."""
        messages = []
        for msg in self.get_all(session_id):
            msg_dict = {"role": msg.role, "content": msg.content}
            messages.append(msg_dict)
        return messages
