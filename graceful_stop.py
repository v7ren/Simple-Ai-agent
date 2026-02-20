"""Graceful stop utilities."""

from typing import List


class GracefulStop:
    """Handle graceful stops with partial results."""
    
    def build_message(self, reason: str) -> str:
        """Build graceful stop message."""
        
        parts = [
            "The agent stopped due to resource constraints.",
            f"Reason: {reason}",
            "",
            "Partial context was preserved. You can:",
            "1. Continue with a simpler version of your request",
            "2. Break your task into smaller, independent parts",
            "3. Increase budget/time limits if available",
        ]
        
        return "\n".join(parts)
    
    def build_next_steps(self, reason: str) -> List[str]:
        """Suggest next steps after graceful stop."""
        
        if "budget" in reason.lower():
            return [
                "Increase max_tool_calls or max_tokens_per_request",
                "Split task into smaller chunks",
            ]
        elif "time" in reason.lower():
            return [
                "Increase max_time_seconds",
                "Make request simpler",
            ]
        else:
            return [
                "Simplify the request",
                "Break into smaller tasks",
            ]
