"""Refusal handler for safe completions."""

from dataclasses import dataclass
from typing import Optional

from context.run_context import RunContext


@dataclass
class RefusalResponse:
    """Refusal response."""
    message: str
    reason: str
    alternative: Optional[str]


class RefusalHandler:
    """Creates safe refusal responses."""
    
    def create_response(
        self,
        reason: str,
        alternative: Optional[str],
        run_context: RunContext,
    ) -> RefusalResponse:
        """Create a refusal response aligned with skill.md policies."""
        
        message_parts = [
            f"I'm unable to help with this request. Reason: {reason}",
        ]
        
        if alternative:
            message_parts.append(f"Alternative: {alternative}")
        
        message_parts.append(
            "If you believe this is an error, please rephrase your request or provide additional context."
        )
        
        return RefusalResponse(
            message=" ".join(message_parts),
            reason=reason,
            alternative=alternative,
        )
