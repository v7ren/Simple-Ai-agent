"""API dependencies for FastAPI."""

from fastapi import Request
from typing import Optional

from config import get_settings, Settings
from context.run_context import RunContext


def get_settings_dep() -> Settings:
    """Dependency to get settings."""
    return get_settings()


def get_run_context(request: Request) -> Optional[RunContext]:
    """Get run context from request state if it exists."""
    return getattr(request.state, "run_context", None)


def set_run_context(request: Request, context: RunContext):
    """Set run context in request state."""
    request.state.run_context = context
