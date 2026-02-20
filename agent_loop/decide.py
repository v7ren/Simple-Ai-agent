"""Decide next step in agent loop."""

from enum import Enum, auto
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from config import Settings
from context.run_context import RunContext


class Action(Enum):
    """Possible actions."""
    CLARIFY = auto()  # Ask clarifying question
    CALL_LLM = auto()  # Call LLM for response
    CALL_TOOL = auto()  # Call a tool directly
    FINISH = auto()  # Complete the task


@dataclass
class Decision:
    """Decision on next step."""
    action: Action
    question: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    final_answer: Optional[str] = None


class DecideModule:
    """Decide next action based on current state."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def decide(
        self,
        user_message: str,
        run_context: RunContext,
        current_step: int,
        last_llm_response: Optional[Dict] = None,
        has_tool_results: bool = False,
    ) -> Decision:
        """Decide next action.
        
        Logic:
        - Step 0: Always call LLM first
        - If LLM returned tool_calls: call tools
        - If LLM returned final answer: finish
        - If budget exhausted: finish
        """
        
        # Check budget
        if not run_context.has_budget_remaining:
            return Decision(
                action=Action.FINISH,
                final_answer="Budget exhausted. Stopping gracefully.",
            )
        
        # Check timeout
        if run_context.is_timed_out:
            return Decision(
                action=Action.FINISH,
                final_answer="Time limit reached. Stopping gracefully.",
            )
        
        # First step: always call LLM
        if current_step == 0:
            return Decision(action=Action.CALL_LLM)
        
        # If we have LLM response
        if last_llm_response:
            # Check for tool_calls
            if last_llm_response.get("tool_calls"):
                return Decision(
                    action=Action.CALL_TOOL,
                    tool_calls=last_llm_response["tool_calls"],
                )
            
            # Check for final answer
            if last_llm_response.get("content"):
                # Check if it looks like a question
                content = last_llm_response["content"].strip()
                if content.endswith("?") and "?" in content[:100]:
                    return Decision(
                        action=Action.CLARIFY,
                        question=content,
                    )
                
                return Decision(
                    action=Action.FINISH,
                    final_answer=content,
                )
        
        # If we have tool results, call LLM to process them
        if has_tool_results:
            return Decision(action=Action.CALL_LLM)
        
        # Default: finish
        return Decision(
            action=Action.FINISH,
            final_answer="Task completed.",
        )
