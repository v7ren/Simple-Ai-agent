"""Model router."""

from typing import Literal
from config import Settings


class ModelRouter:
    """Routes requests to appropriate model based on policy."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def select_model(
        self,
        intent: Literal["draft", "verify", "default"] = "default",
    ) -> str:
        """Select model based on intent.
        
        Args:
            intent: Purpose of the call
                - "draft": Cheaper/faster for initial generation
                - "verify": Stronger model for verification
                - "default": Standard model
        
        Returns:
            Model name for OpenRouter
        """
        if intent == "verify":
            return self.settings.openrouter_verification_model
        elif intent == "draft":
            return self.settings.openrouter_default_model
        else:
            # For most cases, use default (cheaper) model
            return self.settings.openrouter_default_model
    
    def get_cost_estimate(self, model: str, tokens: int) -> float:
        """Estimate cost for request (very rough)."""
        # Simplified cost model - in practice, use actual model pricing
        # These are approximations
        cheap_models = ["gpt-4o-mini", "claude-3-haiku"]
        expensive_models = ["gpt-4", "claude-3-opus"]
        
        if any(m in model.lower() for m in cheap_models):
            return tokens * 0.00001  # ~$0.01 per 1K tokens
        elif any(m in model.lower() for m in expensive_models):
            return tokens * 0.00015  # ~$0.15 per 1K tokens
        else:
            return tokens * 0.00003  # Default rate
