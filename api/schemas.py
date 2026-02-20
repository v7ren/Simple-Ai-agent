"""API schemas for request and response models."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """A single message in the conversation."""
    model_config = ConfigDict(frozen=True)
    
    role: MessageRole
    content: str
    name: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ToolCall(BaseModel):
    """A tool call from the assistant."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result from a tool execution."""
    model_config = ConfigDict(frozen=True)
    
    tool_call_id: str
    name: str
    content: str
    success: bool = True
    duration_ms: Optional[int] = None


class RunStep(BaseModel):
    """One step of the agent loop: LLM reasoning plus tool calls and their results."""
    reasoning: Optional[str] = Field(default=None, description="LLM's thinking before using tools")
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    """Request to run the agent."""
    message: str = Field(..., description="User message", min_length=1, max_length=10000)
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for conversation continuity",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional metadata to attach to the run",
    )


class AgentRunResponse(BaseModel):
    """Response from the agent."""
    run_id: str
    session_id: str
    message: str
    is_final: bool = True
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    steps: list[RunStep] = Field(
        default_factory=list,
        description="Per-step reasoning and tool I/O (thinking, tool calls, tool results)",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="If True, agent is waiting for user to reply 'confirm' before running tools",
    )
    pending_state: Optional[dict[str, Any]] = Field(
        default=None,
        description="Internal: saved on server when requires_confirmation is True; used when user says 'confirm'",
    )
    usage: Optional[dict[str, int]] = None
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    next_steps: list[str] = Field(default_factory=list)


class ClarifyingQuestionResponse(BaseModel):
    """Response when clarifying question is needed."""
    run_id: str
    session_id: str
    question: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RefusalResponse(BaseModel):
    """Response when request is refused."""
    run_id: str
    session_id: str
    refusal_reason: str
    safe_alternative: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
