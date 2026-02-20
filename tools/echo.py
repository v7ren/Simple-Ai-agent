"""Echo tool: echo a message back (for testing)."""

from datetime import datetime
from typing import Dict, Any


async def echo_tool(message: str) -> Dict[str, Any]:
    """Echo a message back."""
    return {"echo": message, "timestamp": datetime.utcnow().isoformat()}


TOOL = {
    "name": "echo",
    "description": "Echo a message back for testing",
    "parameters": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to echo",
            },
        },
        "required": ["message"],
    },
    "handler": echo_tool,
}
