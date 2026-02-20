"""Tool registry: register and execute tools."""

from typing import Dict, List, Callable, Any, Awaitable, Optional
from dataclasses import dataclass
import asyncio


@dataclass
class ToolDefinition:
    """Definition of a tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Awaitable[Any]],
    ) -> None:
        """Register a tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def get_tool(self, name: str) -> ToolDefinition:
        """Get tool by name."""
        return self._tools[name]

    def has_tool(self, name: str) -> bool:
        """Check if tool exists."""
        return name in self._tools

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        on_stream: Optional[Callable[[str, str], None]] = None,
        run_in_separate_shell: Optional[bool] = None,
        session_id: Optional[str] = None,
    ) -> Any:
        """Execute a tool with arguments. session_id is passed to shell tools."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")

        tool = self._tools[name]
        kwargs = dict(arguments)
        if name == "run_python":
            if on_stream is not None:
                kwargs["on_stream"] = on_stream
            if run_in_separate_shell is not None:
                kwargs["run_in_separate_shell"] = run_in_separate_shell
        if name in ("open_shell", "run_shell_command", "close_shell") and session_id is not None:
            kwargs["session_id"] = session_id

        if asyncio.iscoroutinefunction(tool.handler):
            return await tool.handler(**kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: tool.handler(**kwargs))
