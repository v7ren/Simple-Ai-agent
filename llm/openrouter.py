"""OpenRouter client."""

import httpx
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from config import Settings


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: Optional[str]
    tool_calls: List[Dict[str, Any]]
    usage: Dict[str, int]
    model: str
    finish_reason: str


@dataclass
class LLMError:
    """LLM error."""
    message: str
    status_code: Optional[int] = None
    retryable: bool = False


class OpenRouterClient:
    """Client for OpenRouter API."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://localhost",
                "X-Title": settings.agent_name,
            },
            timeout=60.0,
        )
    
    async def chat_completions(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = 0.7,
        stream: bool = False,
    ) -> LLMResponse:
        """Send chat completion request."""
        
        model = model or self.settings.openrouter_default_model
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            payload["tools"] = tools
        
        if tool_choice:
            payload["tool_choice"] = tool_choice
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_response(data, model)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            return LLMResponse(
                content=error_msg,
                tool_calls=[],
                usage={},
                model=model,
                finish_reason="error",
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                tool_calls=[],
                usage={},
                model=model,
                finish_reason="error",
            )
    
    def _parse_response(self, data: Dict[str, Any], model: str) -> LLMResponse:
        """Parse OpenRouter response."""
        
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content=None,
                tool_calls=[],
                usage=data.get("usage", {}),
                model=model,
                finish_reason="empty",
            )
        
        choice = choices[0]
        message = choice.get("message", {})
        
        # Extract content and tool calls
        content = message.get("content")
        tool_calls = []
        
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            if tc.get("type") == "function":
                func = tc.get("function", {})
                tool_calls.append({
                    "id": tc.get("id"),
                    "name": func.get("name"),
                    "arguments": func.get("arguments"),
                })
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            model=model,
            finish_reason=choice.get("finish_reason", "unknown"),
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
