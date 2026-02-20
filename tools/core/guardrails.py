"""Tool guardrails: safety checks on tool arguments."""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import re

from config import Settings
from pipeline.policy import PolicyEngine


@dataclass
class GuardrailResult:
    """Result of guardrail check."""
    allowed: bool
    reason: str = ""
    redacted_args: Optional[Dict[str, Any]] = None


class ToolGuardrails:
    """Guardrails for tool execution."""

    SECRET_PATTERNS = [
        r'sk-[a-zA-Z0-9]{32,}',
        r'[a-zA-Z0-9]{32,64}',
        r'password\s*[=:]\s*\S+',
        r'secret\s*[=:]\s*\S+',
        r'token\s*[=:]\s*\S+',
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.policy = PolicyEngine(settings)

    def check_args(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> GuardrailResult:
        """Check tool arguments against guardrails."""
        args_str = str(arguments)
        redacted = self._redact_secrets(arguments)

        if self._has_dangerous_content(args_str):
            return GuardrailResult(
                allowed=False,
                reason="Tool arguments contain potentially dangerous content",
                redacted_args=redacted,
            )
        if len(args_str) > 10000:
            return GuardrailResult(
                allowed=False,
                reason="Tool arguments exceed size limit",
                redacted_args=redacted,
            )
        return GuardrailResult(allowed=True, redacted_args=redacted)

    def _redact_secrets(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Redact secrets from arguments."""
        import copy
        redacted = copy.deepcopy(arguments)

        def redact_value(value):
            if isinstance(value, str):
                result = value
                for pattern in self.SECRET_PATTERNS:
                    result = re.sub(pattern, '[REDACTED]', result, flags=re.IGNORECASE)
                return result
            elif isinstance(value, dict):
                return {k: redact_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [redact_value(item) for item in value]
            return value

        return {k: redact_value(v) for k, v in redacted.items()}

    def _has_dangerous_content(self, text: str) -> bool:
        """Check for dangerous content."""
        danger_patterns = [
            r'rm\s+-rf',
            r'(?:bash|sh)\s+-c',
            r'eval\s*\(',
            r'exec\s*\(',
        ]
        text_lower = text.lower()
        for pattern in danger_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
