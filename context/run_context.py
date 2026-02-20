"""Run context for agent execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Set
import uuid


@dataclass
class RunContext:
    """Context for a single agent run."""
    
    session_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.utcnow)
    max_time_seconds: int = 180
    max_tool_calls: int = 15
    max_tokens_per_request: int = 64000
    max_cost_per_request: float = 5.0
    
    # Runtime tracking
    tool_calls_count: int = 0
    total_tokens_used: int = 0
    current_cost: float = 0.0
    
    # State tracking
    completed: bool = False
    stopped: bool = False
    stop_reason: str = ""
    
    # Memory tracking
    memories_written: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        if not self.run_id:
            self.run_id = str(uuid.uuid4())
    
    @property
    def elapsed_seconds(self) -> float:
        """Time elapsed since run started."""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def is_timed_out(self) -> bool:
        """Check if run has exceeded max time."""
        return self.elapsed_seconds >= self.max_time_seconds
    
    @property
    def has_budget_remaining(self) -> bool:
        """Check if any budget is remaining."""
        if self.tool_calls_count >= self.max_tool_calls:
            return False
        if self.total_tokens_used >= self.max_tokens_per_request:
            return False
        if self.current_cost >= self.max_cost_per_request:
            return False
        return True
    
    def record_tool_call(self):
        """Record a tool call."""
        self.tool_calls_count += 1
    
    def record_tokens(self, tokens: int):
        """Record tokens used."""
        self.total_tokens_used += tokens
    
    def record_cost(self, cost: float):
        """Record cost incurred."""
        self.current_cost += cost
    
    def mark_stopped(self, reason: str):
        """Mark run as stopped with reason."""
        self.stopped = True
        self.stop_reason = reason
    
    def mark_completed(self):
        """Mark run as completed."""
        self.completed = True
    
    def get_budget_exceeded_reason(self) -> str:
        """Return which budget was exceeded and current vs limit (for user feedback)."""
        if self.tool_calls_count >= self.max_tool_calls:
            return f"Tool call limit reached ({self.tool_calls_count}/{self.max_tool_calls}). Increase MAX_TOOL_CALLS in .env"
        if self.total_tokens_used >= self.max_tokens_per_request:
            return f"Token limit reached (used {self.total_tokens_used}, limit {self.max_tokens_per_request}). Increase MAX_TOKENS_PER_REQUEST in .env"
        if self.current_cost >= self.max_cost_per_request:
            return f"Cost limit reached (${self.current_cost:.2f}, limit ${self.max_cost_per_request:.2f}). Increase MAX_COST_PER_REQUEST in .env"
        return "Budget exhausted"

    def get_status(self) -> dict:
        """Get run status summary."""
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "tool_calls_count": self.tool_calls_count,
            "total_tokens_used": self.total_tokens_used,
            "current_cost": round(self.current_cost, 4),
            "has_budget_remaining": self.has_budget_remaining,
            "is_timed_out": self.is_timed_out,
            "completed": self.completed,
            "stopped": self.stopped,
            "stop_reason": self.stop_reason,
        }
