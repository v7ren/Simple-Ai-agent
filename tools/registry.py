"""Tool registry and default tool registration. Tools are defined in tools/*.py."""

from tools.core.registry import ToolRegistry
from tools.echo import TOOL as ECHO_TOOL
from tools.search import TOOL as SEARCH_TOOL
from tools.run_python import TOOL as RUN_PYTHON_TOOL
from tools.shell import TOOL_OPEN, TOOL_RUN, TOOL_CLOSE, TOOL_OPEN_WINDOW, TOOL_STOP_SERVER


def create_default_registry() -> ToolRegistry:
    """Create registry with all built-in tools (one per tools/*.py module)."""
    registry = ToolRegistry()
    for tool_def in (
        ECHO_TOOL,
        SEARCH_TOOL,
        RUN_PYTHON_TOOL,
        TOOL_OPEN,
        TOOL_RUN,
        TOOL_CLOSE,
        TOOL_OPEN_WINDOW,
        TOOL_STOP_SERVER,
    ):
        registry.register(
            name=tool_def["name"],
            description=tool_def["description"],
            parameters=tool_def["parameters"],
            handler=tool_def["handler"],
        )
    return registry
