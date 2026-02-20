"""Configuration settings for the AI agent."""

from pydantic import Field, computed_field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter Configuration
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter base URL",
    )
    openrouter_default_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Default model for drafting",
    )
    openrouter_verification_model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        description="Stronger model for verification",
    )

    # Agent Configuration
    agent_name: str = Field(
        default="Agent",
        description="Name of the agent",
    )
    agent_description: str = Field(
        default="An AI agent that helps users achieve goals",
        description="Description of the agent",
    )

    # Budget Limits (per agent run: search + answer often needs 2–3 LLM calls + tools)
    max_tool_calls: int = Field(
        default=15,
        description="Maximum number of tool calls per request",
        ge=1,
        le=100,
    )
    max_time_seconds: int = Field(
        default=180,
        description="Maximum wall time in seconds",
        ge=10,
        le=600,
    )
    max_tokens_per_request: int = Field(
        default=64000,
        description="Maximum total tokens across all LLM calls in one run",
        ge=1000,
        le=128000,
    )
    max_cost_per_request: float = Field(
        default=5.0,
        description="Maximum cost per request in USD",
        ge=0.01,
        le=50.0,
    )

    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="Requests per minute per user/session",
        ge=1,
        le=1000,
    )

    # Memory Configuration
    stm_max_turns: int = Field(
        default=20,
        description="Maximum number of recent conversation turns to keep in STM",
        ge=5,
        le=100,
    )
    ltm_enabled: bool = Field(
        default=False,
        description="Enable long-term memory",
    )
    retrieval_enabled: bool = Field(
        default=False,
        description="Enable semantic retrieval",
    )
    retrieval_top_k: int = Field(
        default=5,
        description="Number of top chunks to retrieve",
        ge=1,
        le=20,
    )

    # Tools Configuration (comma-separated in env, e.g. ALLOWED_TOOLS=echo,search or ALLOWED_TOOLS=* for all)
    allowed_tools_str: str = Field(
        default="*",
        description="Comma-separated allowed tool names; empty or * = all tools allowed",
        validation_alias=AliasChoices("allowed_tools", "ALLOWED_TOOLS"),
    )

    # Auth Configuration
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for authentication",
    )
    jwt_secret: Optional[str] = Field(
        default=None,
        description="JWT secret for token verification",
    )

    # Agent mode: "free" = no policy/guardrails + user must type "confirm" before each tool run; "restrained" = policy, abuse, tool guardrails and quality checks on, tools run without confirmation
    agent_mode: Literal["free", "restrained"] = Field(
        default="free",
        description="'free': unrestrained, require typing 'confirm' before tools. 'restrained': policy/guardrails on, no confirm.",
        validation_alias=AliasChoices("AGENT_MODE", "agent_mode"),
    )

    # Run Python tool in a separate visible shell window (Windows: new CMD window; you see output there instead of in the agent CLI)
    run_python_in_separate_shell: bool = Field(
        default=True,
        description="If True, run_python opens a new CMD/shell window so you see the script run there.",
        validation_alias=AliasChoices("RUN_PYTHON_IN_SEPARATE_SHELL", "run_python_in_separate_shell"),
    )

    # Safety Configuration
    max_input_length: int = Field(
        default=10000,
        description="Maximum input length in characters",
        ge=100,
        le=100000,
    )
    blocked_keywords_str: str = Field(
        default="",
        description="Comma-separated blocked keywords for abuse detection",
        validation_alias=AliasChoices("blocked_keywords", "BLOCKED_KEYWORDS"),
    )

    @computed_field
    @property
    def disable_restraints(self) -> bool:
        """True when agent_mode is 'free' (policy/guardrails skipped)."""
        return self.agent_mode == "free"

    @computed_field
    @property
    def require_user_confirm(self) -> bool:
        """True when agent_mode is 'free' (user must type 'confirm' before tools run)."""
        return self.agent_mode == "free"

    @computed_field
    @property
    def allowed_tools(self) -> list[str]:
        """Parsed list of allowed tool names from env. Empty or '*' means all tools allowed."""
        s = (self.allowed_tools_str or "").strip()
        if s in ("", "*"):
            return []
        return [x.strip() for x in self.allowed_tools_str.split(",") if x.strip()]

    @computed_field
    @property
    def blocked_keywords(self) -> list[str]:
        """Parsed list of blocked keywords from env."""
        return [x.strip() for x in self.blocked_keywords_str.split(",") if x.strip()]


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
