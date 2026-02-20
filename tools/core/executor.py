"""Tool executor and observation builder."""

import time
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass

from tools.core.registry import ToolRegistry


@dataclass
class ToolExecutionResult:
    """Result of tool execution."""
    success: bool
    content: str
    duration_ms: int
    error: Optional[str] = None


@dataclass
class ToolObservation:
    """Observation built from tool result."""
    summary: str
    raw_payload: Any
    citation: Optional[str] = None


class ToolExecutor:
    """Executes tools and builds observations."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        on_stream: Optional[Callable[[str, str], None]] = None,
        run_in_separate_shell: Optional[bool] = None,
        session_id: Optional[str] = None,
    ) -> ToolExecutionResult:
        """Execute a tool and return result. session_id is passed to shell tools."""
        start_time = time.time()

        try:
            result = await self.registry.execute(
                tool_name,
                arguments,
                on_stream=on_stream,
                run_in_separate_shell=run_in_separate_shell,
                session_id=session_id,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            import json
            if isinstance(result, (dict, list)):
                content = json.dumps(result, indent=2)
            else:
                content = str(result)
            return ToolExecutionResult(
                success=True,
                content=content,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolExecutionResult(
                success=False,
                content="",
                duration_ms=duration_ms,
                error=str(e),
            )


class ObservationBuilder:
    """Build observations from tool results."""

    def build(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: ToolExecutionResult,
    ) -> ToolObservation:
        """Build observation from tool result."""
        if result.success:
            args_summary = ", ".join(f"{k}={v}" for k, v in arguments.items())
            summary = f"Tool '{tool_name}' called with ({args_summary}) succeeded."
            try:
                import json
                data = json.loads(result.content)
                if isinstance(data, dict):
                    if "results" in data:
                        summary += f" Found {len(data['results'])} result(s)."
                    elif "echo" in data:
                        summary += f" Echo: {data['echo']}"
            except Exception:
                pass
            return ToolObservation(summary=summary, raw_payload=result.content)
        return ToolObservation(
            summary=f"Tool '{tool_name}' failed: {result.error}",
            raw_payload=None,
            citation=None,
        )
