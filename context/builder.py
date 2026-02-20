"""Context builder for assembling prompts."""

from typing import List, Optional, Dict, Any
from config import Settings
from context.run_context import RunContext
from context.stm import ShortTermMemory, MemoryMessage
from context.ltm import LongTermMemoryStore
from context.retrieval import RetrievalEngine
from pipeline.input import NormalizedInput
from tools.registry import ToolRegistry


class ContextBuilder:
    """Builds complete prompt context from STM, LTM, and other sources."""
    
    def __init__(
        self,
        settings: Settings,
        stm: ShortTermMemory,
        ltm: LongTermMemoryStore,
        retrieval: RetrievalEngine,
        tools: ToolRegistry,
    ):
        self.settings = settings
        self.stm = stm
        self.ltm = ltm
        self.retrieval = retrieval
        self.tools = tools
    
    def build(
        self,
        user_message: str,
        session_id: str,
        run_context: RunContext,
        tool_results: Optional[List[dict]] = None,
        last_assistant_message: Optional[dict] = None,
    ) -> List[dict]:
        """Build complete message context for LLM."""
        
        messages = []
        
        # 1. System prompt
        system_prompt = self._build_system_prompt(run_context)
        messages.append({"role": "system", "content": system_prompt})
        
        # 2. Developer instructions
        dev_prompt = self._build_developer_prompt()
        messages.append({"role": "developer", "content": dev_prompt})
        
        # 3. Retrieved context (if enabled)
        if self.settings.retrieval_enabled:
            retrieved = self._get_retrieved_context(session_id, user_message)
            if retrieved:
                messages.append({"role": "system", "content": retrieved})
        
        # 4. Recent conversation from STM
        recent_messages = self.stm.to_messages(session_id)
        messages.extend(recent_messages)
        
        # 5. Assistant message that requested tools (so API sees correct order)
        if last_assistant_message:
            messages.append(last_assistant_message)
        
        # 6. Tool results (if any)
        if tool_results:
            for result in tool_results:
                messages.append({
                    "role": "tool",
                    "content": result.get("content", ""),
                    "tool_call_id": result.get("tool_call_id") or result.get("id", ""),
                })
        
        # 7. Current user message (skip if already last in STM — we append user at start of each run)
        if not recent_messages or recent_messages[-1].get("role") != "user" or recent_messages[-1].get("content") != user_message:
            messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _build_system_prompt(self, run_context: RunContext) -> str:
        """Build system prompt from skill.md template."""
        
        # Load system prompt template (UTF-8 for Windows compatibility)
        try:
            with open("prompts/system.txt", "r", encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError:
            # Fallback to basic system prompt
            template = self._default_system_prompt()
        
        # Substitute placeholders
        system_prompt = template.replace("<Your Agent Name>", self.settings.agent_name)
        system_prompt = system_prompt.replace("<N>", str(self.settings.max_tool_calls))
        system_prompt = system_prompt.replace("<T>", str(self.settings.max_time_seconds))
        system_prompt = system_prompt.replace("<budget>", f"{self.settings.max_cost_per_request:.2f}")
        
        return system_prompt
    
    def _build_developer_prompt(self) -> str:
        """Build developer prompt with constraints and tools reference."""
        parts = [
            "You have access to the following tools:",
        ]
        for tool in self.tools.list_tools():
            parts.append(f"- {tool['name']}: {tool['description']}")
        parts.extend([
            "",
            "Constraints:",
            f"- Maximum tool calls per request: {self.settings.max_tool_calls}",
            f"- Maximum response time: {self.settings.max_time_seconds}s",
            f"- Be concise and structured in your responses.",
        ])
        # Append tools.md so the LLM knows how to use each tool
        try:
            with open("tools/tools.md", "r", encoding="utf-8") as f:
                parts.append("")
                parts.append("---")
                parts.append(f.read())
        except FileNotFoundError:
            pass
        return "\n".join(parts)
    
    def _get_retrieved_context(self, session_id: str, query: str) -> str:
        """Retrieve and format relevant memories."""
        memories = self.retrieval.search(
            session_id=session_id,
            query=query,
            top_k=self.settings.retrieval_top_k,
        )
        return self.retrieval.format_for_context(memories)
    
    def _default_system_prompt(self) -> str:
        """Default system prompt if file not found."""
        return f"""You are {self.settings.agent_name}. {self.settings.agent_description}

Mission:
- Solve the user's task correctly and efficiently.
- Be safe, honest, and privacy-preserving.
- Minimize cost and latency while maintaining quality.

Operating Principles:
1. Truthfulness: If you don't know, say so. Don't invent facts.
2. Tool honesty: Only claim you did something if a tool confirms it.
3. User intent first: Optimize for what the user wants to accomplish.
4. Ask when blocked: If requirements are ambiguous, ask clarifying questions.
5. Safety & policy: Refuse disallowed requests; offer safe alternatives.

Workflow:
1. Understand the goal and identify missing details.
2. Decide: ask question, answer directly, or use tools.
3. Plan: create a short internal plan.
4. Execute: use minimum tools needed, validate inputs, handle failures.
5. Verify: check for contradictions or issues.
6. Deliver: provide final output, offer next steps.

Tool Calling:
- Use tools when they materially increase correctness.
- Max tool calls per request: <N>
- Time limit: <T> seconds.
- Never fabricate tool results.

Memory:
- Short-term: use conversation context.
- Long-term: store only durable, user-approved info (preferences, stable facts).
- Never store secrets or sensitive data.
- When deciding to remember, ask: "Should I remember this?"

Response Style:
- Be concise, structured, and actionable.
- Use markdown headings and bullets.
- Include minimal, runnable code examples when relevant.
- If refusing: brief reason + safe alternative.
"""