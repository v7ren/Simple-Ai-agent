"""Prompt composer."""

from typing import List, Dict, Any, Optional
from config import Settings
from context.run_context import RunContext
from tools.registry import ToolRegistry


class PromptComposer:
    """Composes prompts for LLM."""
    
    def __init__(self, settings: Settings, tools: ToolRegistry):
        self.settings = settings
        self.tools = tools
    
    def compose(
        self,
        messages: List[Dict[str, str]],
        include_tools: bool = True,
    ) -> Dict[str, Any]:
        """Compose request payload with tool definitions."""
        
        payload = {
            "messages": messages,
        }
        
        if include_tools:
            tool_definitions = self._get_tool_definitions()
            if tool_definitions:
                payload["tools"] = tool_definitions
        
        return payload
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in OpenAI format."""
        definitions = []
        
        for tool in self.tools.list_tools():
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            })
        
        return definitions


class ParseValidator:
    """Parse and validate LLM responses."""
    
    def __init__(self):
        self.max_repair_attempts = 3
    
    def validate_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        tools: ToolRegistry,
    ) -> tuple[bool, str]:
        """Validate tool calls against tool registry.
        
        Returns:
            (is_valid, error_message)
        """
        for tc in tool_calls:
            name = tc.get("name")
            if not name:
                return False, "Tool call missing name"
            
            if not tools.has_tool(name):
                return False, f"Unknown tool: {name}"
            
            # Validate arguments match schema
            tool = tools.get_tool(name)
            args = tc.get("arguments")
            
            if args is None:
                return False, f"Tool '{name}' missing arguments"
            
            # Basic validation: should be valid JSON if string
            if isinstance(args, str):
                import json
                try:
                    json.loads(args)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON in tool arguments: {e}"
        
        return True, ""
    
    def create_repair_prompt(
        self,
        original_response: str,
        error: str,
        attempt: int,
    ) -> str:
        """Create prompt to repair invalid response."""
        
        repairs = [
            f"Your previous response had an error: {error}",
            "Please provide a valid response with proper JSON formatting.",
            "When calling tools, use the exact tool names and valid JSON arguments.",
        ]
        
        if attempt > 1:
            repairs.append("Previous repair attempts failed. Be extra careful with JSON formatting.")
        
        return "\n".join(repairs)
