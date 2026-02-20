"""Authentication, rate limiting, and abuse checks."""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime, timedelta
from typing import Optional, Set
import hashlib

from config import Settings


# Rate limiter using remote address as key
limiter = Limiter(key_func=get_remote_address)

# Security scheme for optional API key auth
security = HTTPBearer(auto_error=False)


class AbuseChecker:
    """Abuse detection and prevention."""
    
    def __init__(self, settings: Settings):
        self.max_input_length = settings.max_input_length
        self.blocked_keywords = set(k.lower() for k in settings.blocked_keywords)
        self._abuse_history: dict[str, list[datetime]] = {}
        self._abuse_window = timedelta(minutes=5)
        self._max_requests_per_window = 30
    
    def check_input_length(self, message: str) -> bool:
        """Check if input length is within limits."""
        return len(message) <= self.max_input_length
    
    def check_blocked_keywords(self, message: str) -> bool:
        """Check if message contains blocked keywords."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.blocked_keywords)
    
    def check_rate_anomaly(self, client_id: str) -> bool:
        """Check if client is making suspiciously many requests."""
        now = datetime.utcnow()
        if client_id not in self._abuse_history:
            self._abuse_history[client_id] = []
        
        # Clean old entries
        self._abuse_history[client_id] = [
            t for t in self._abuse_history[client_id]
            if now - t < self._abuse_window
        ]
        
        # Check threshold
        if len(self._abuse_history[client_id]) > self._max_requests_per_window:
            return False
        
        self._abuse_history[client_id].append(now)
        return True
    
    def check(self, message: str, client_id: str) -> Optional[str]:
        """Run all abuse checks. Returns error message if check fails, None if ok."""
        if not self.check_input_length(message):
            return f"Input exceeds maximum length of {self.max_input_length} characters"
        
        if self.check_blocked_keywords(message):
            return "Input contains disallowed content"
        
        if not self.check_rate_anomaly(client_id):
            return "Rate limit exceeded - too many requests in short period"
        
        return None


def get_client_id(request: Request) -> str:
    """Get a unique identifier for the client."""
    # Try X-Forwarded-For header first (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Fall back to direct client IP
    client_host = request.client.host if request.client else "unknown"
    
    # Hash for privacy
    return hashlib.sha256(client_host.encode()).hexdigest()[:16]


def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials],
    settings: Settings,
) -> bool:
    """Verify API key if configured."""
    if not settings.api_key:
        # No API key required
        return True
    
    if not credentials:
        return False
    
    # Simple string comparison (in production use constant-time comparison)
    return credentials.credentials == settings.api_key


def raise_auth_error():
    """Raise authentication error."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def raise_rate_limit_error():
    """Raise rate limit error."""
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded - please slow down",
    )


def raise_abuse_error(message: str):
    """Raise abuse detection error."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Request blocked: {message}",
    )
