"""Policy and safety guardrails."""

from dataclasses import dataclass
from typing import Optional

from config import Settings


@dataclass
class PolicyResult:
    """Result of policy check."""
    allowed: bool
    reason: str = ""
    alternative: Optional[str] = None


class PolicyEngine:
    """Policy and safety guardrails."""
    
    # Common disallowed categories
    DISALLOWED_PATTERNS = [
        "hacking",
        "exploit",
        "vulnerability",
        "weapon",
        "bomb",
        "malware",
        "ransomware",
        "phishing",
        "social engineering",
        "credit card",
        "ssn",
        "social security",
        "password",
        "api key",
        "secret key",
    ]
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.allowed_tools = set(settings.allowed_tools)
    
    def check(self, normalized_input) -> PolicyResult:
        """Check input against policies. Returns PolicyResult."""
        content_lower = normalized_input.content.lower()
        
        # Check for disallowed content
        for pattern in self.DISALLOWED_PATTERNS:
            if pattern in content_lower:
                return PolicyResult(
                    allowed=False,
                    reason=f"Request appears to involve {pattern}",
                    alternative="If you have a legitimate security research question, please provide more context about your authorized security testing environment.",
                )
        
        return PolicyResult(allowed=True)
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is in the allowlist."""
        if not self.allowed_tools:
            # If no allowlist specified, all tools are allowed
            return True
        return tool_name in self.allowed_tools
    
    def redact_secrets(self, text: str) -> str:
        """Redact common secret patterns from text."""
        import re
        
        # Patterns to redact
        patterns = [
            (r'(api[_-]?key\s*[:=]\s*)["\']?[\w-]+["\']?', r'\1***REDACTED***'),
            (r'(secret[_-]?key\s*[:=]\s*)["\']?[\w-]+["\']?', r'\1***REDACTED***'),
            (r'(password\s*[:=]\s*)["\']?[^"\'\s]+["\']?', r'\1***REDACTED***'),
            (r'(token\s*[:=]\s*)["\']?[\w-]+["\']?', r'\1***REDACTED***'),
            (r'(bearer\s+)[\w-]+', r'\1***REDACTED***'),
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
