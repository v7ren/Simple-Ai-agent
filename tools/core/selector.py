"""Tool selector: validate and filter LLM tool calls."""

from typing import List, Dict, Any, Tuple
from config import Settings
from tools.core.registry import ToolRegistry


class ToolSelector:
    """Select and validate tools from LLM tool_calls."""

    def __init__(self, registry: ToolRegistry, settings: Settings):
        self.registry = registry
        self.settings = settings

    def select(
        self,
        tool_calls: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Select and validate tools. Returns (valid_tool_calls, error_messages)."""
        valid = []
        errors = []

        for tc in tool_calls:
            name = tc.get("name")
            tc_id = tc.get("id", "unknown")

            if not self.registry.has_tool(name):
                errors.append(f"Tool '{name}' (id: {tc_id}) not found in registry")
                continue

            if self.settings.allowed_tools and name not in self.settings.allowed_tools:
                errors.append(f"Tool '{name}' is not in the allowed tools list")
                continue

            args = tc.get("arguments")
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON in tool '{name}' arguments: {e}")
                    continue

            valid.append({
                "id": tc_id,
                "name": name,
                "arguments": args or {},
            })

        return valid, errors
