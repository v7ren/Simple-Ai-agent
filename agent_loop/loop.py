"""Main agent loop."""

import time
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta

from config import Settings
from context.run_context import RunContext
from context.stm import ShortTermMemory
from context.ltm import LongTermMemoryStore
from context.retrieval import RetrievalEngine
from context.builder import ContextBuilder
from llm.openrouter import OpenRouterClient
from llm.router import ModelRouter
from llm.prompt import PromptComposer, ParseValidator
from tools.registry import ToolRegistry, create_default_registry
from tools.selector import ToolSelector
from tools.guardrails import ToolGuardrails
from tools.executor import ToolExecutor, ObservationBuilder, ToolExecutionResult
from agent_loop.decide import DecideModule, Action
from api.schemas import AgentRunResponse, ToolCall, ToolResult, RunStep
from memory_write import MemoryWriter
from quality import QualityChecker
from graceful_stop import GracefulStop


class AgentLoop:
    """Main agent execution loop."""

    def __init__(self, settings: Settings, stm: Optional[ShortTermMemory] = None):
        self.settings = settings
        self.stm = stm if stm is not None else ShortTermMemory(max_turns=settings.stm_max_turns)
        self.ltm = LongTermMemoryStore() if settings.ltm_enabled else None
        self.retrieval = RetrievalEngine(self.ltm) if self.ltm else None
        
        # Tools
        self.tools = create_default_registry()
        self.tool_selector = ToolSelector(self.tools, settings)
        self.tool_guardrails = ToolGuardrails(settings)
        self.tool_executor = ToolExecutor(self.tools)
        self.observation_builder = ObservationBuilder()
        
        # LLM
        self.llm_client = OpenRouterClient(settings)
        self.model_router = ModelRouter(settings)
        self.prompt_composer = PromptComposer(settings, self.tools)
        self.parse_validator = ParseValidator()
        
        # Context
        self.context_builder = ContextBuilder(
            settings=settings,
            stm=self.stm,
            ltm=self.ltm,
            retrieval=self.retrieval,
            tools=self.tools,
        )
        
        # Logic modules
        self.decide = DecideModule(settings)
        self.memory_writer = MemoryWriter(self.ltm, settings) if self.ltm else None
        self.quality_checker = QualityChecker(settings)
        self.graceful_stop = GracefulStop()
    
    async def run(
        self,
        user_message: str,
        session_id: str,
        run_context: RunContext,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentRunResponse:
        """Run the agent loop. If on_event is set, call it with progress events (reasoning, tool_call, tool_result, message, done)."""
        
        start_time = time.time()
        step = 0
        last_llm_response: Optional[Dict] = None
        last_assistant_message_for_api: Optional[Dict] = None  # OpenAI-format so API sees tool_calls + results
        tool_results_history: List[Dict] = []
        all_tool_calls: List[ToolCall] = []
        all_tool_results: List[ToolResult] = []
        run_steps: List[RunStep] = []

        def emit(ev: Dict[str, Any]) -> None:
            if on_event:
                on_event(ev)

        try:
            # Remember this turn's user message so conversation history is complete for future turns
            self.stm.append(session_id, "user", user_message)

            while True:
                # Check budget
                if not run_context.has_budget_remaining:
                    reason = run_context.get_budget_exceeded_reason()
                    return self._graceful_stop(
                        reason, run_context, start_time,
                        all_tool_calls, all_tool_results, run_steps, emit,
                    )
                
                if run_context.is_timed_out:
                    return self._graceful_stop(
                        "Time limit reached", run_context, start_time,
                        all_tool_calls, all_tool_results, run_steps, emit,
                    )
                
                # Decide next action
                decision = self.decide.decide(
                    user_message=user_message,
                    run_context=run_context,
                    current_step=step,
                    last_llm_response=last_llm_response,
                    has_tool_results=len(tool_results_history) > 0,
                )
                
                if decision.action == Action.CLARIFY:
                    # Return clarifying question
                    duration_ms = int((time.time() - start_time) * 1000)
                    emit({"type": "reasoning", "content": decision.question})
                    # Save to STM
                    self.stm.append(session_id, "assistant", decision.question)
                    r = AgentRunResponse(
                        run_id=run_context.run_id,
                        session_id=session_id,
                        message=decision.question,
                        is_final=False,
                        tool_calls=all_tool_calls,
                        tool_results=all_tool_results,
                        steps=run_steps,
                        duration_ms=duration_ms,
                    )
                    emit({"type": "done", "response": r.model_dump(mode="json")})
                    return r
                
                elif decision.action == Action.CALL_LLM:
                    # Build context and call LLM
                    has_tool_results = len(tool_results_history) > 0
                    if step == 0:
                        build_user_message = user_message
                    else:
                        build_user_message = (
                            "Using the tool results above, provide your final answer to the user. Do not call additional tools unless strictly necessary."
                            if has_tool_results
                            else "Continue based on tool results."
                        )
                    messages = self.context_builder.build(
                        user_message=build_user_message,
                        session_id=session_id,
                        run_context=run_context,
                        tool_results=tool_results_history if has_tool_results else None,
                        last_assistant_message=last_assistant_message_for_api if has_tool_results else None,
                    )

                    # Select model
                    model = self.model_router.select_model("draft")
                    
                    # Call LLM (pass OpenAI-format tool definitions with type + function)
                    tool_defs = self.prompt_composer._get_tool_definitions() if step == 0 else None
                    response = await self.llm_client.chat_completions(
                        messages=messages,
                        model=model,
                        tools=tool_defs,
                        max_tokens=min(4000, self.settings.max_tokens_per_request),
                    )
                    
                    # Update budget
                    tokens_used = response.usage.get("total_tokens", 0)
                    run_context.record_tokens(tokens_used)
                    
                    # Parse response
                    last_llm_response = {
                        "content": response.content,
                        "tool_calls": response.tool_calls,
                        "finish_reason": response.finish_reason,
                    }
                    if response.content and response.content.strip():
                        emit({"type": "reasoning", "content": response.content})
                    # Store assistant message in API format so next request has assistant -> tool results order
                    if response.tool_calls:
                        import json
                        last_assistant_message_for_api = {
                            "role": "assistant",
                            "content": response.content or None,
                            "tool_calls": [
                                {
                                    "id": tc.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("name"),
                                        "arguments": json.dumps(tc["arguments"]) if isinstance(tc.get("arguments"), dict) else (tc.get("arguments") or "{}"),
                                    },
                                }
                                for tc in response.tool_calls
                            ],
                        }
                        # Only send tool results that match this assistant message (clear previous round)
                        tool_results_history.clear()
                    else:
                        last_assistant_message_for_api = None
                    
                    # Save to STM
                    if response.content:
                        self.stm.append(session_id, "assistant", response.content)

                elif decision.action == Action.CALL_TOOL:
                    # Execute tool calls (or ask for confirmation)
                    if decision.tool_calls:
                        valid_tools, errors = self.tool_selector.select(decision.tool_calls)
                        if errors and not valid_tools:
                            last_llm_response = {
                                "content": f"Tool validation errors: {'; '.join(errors)}",
                                "tool_calls": [],
                            }
                            continue
                        # Require user to type "confirm" before running tools
                        if self.settings.require_user_confirm:
                            lines = []
                            for tc in valid_tools:
                                name = tc.get("name", "?")
                                args = tc.get("arguments") or {}
                                if name == "run_python" and "code" in args:
                                    lines.append(f"run_python:\n```\n{args.get('code', '')}\n```")
                                else:
                                    import json as _json
                                    lines.append(f"{name}({_json.dumps(args)})")
                            msg = "I want to run:\n" + "\n".join(lines) + "\n\nType **confirm** to run."
                            pending_state = {
                                "user_message": user_message,
                                "assistant_message": last_assistant_message_for_api,
                                "tool_calls": [{"id": tc.get("id"), "name": tc.get("name"), "arguments": tc.get("arguments") or {}} for tc in valid_tools],
                            }
                            duration_ms = int((time.time() - start_time) * 1000)
                            r = AgentRunResponse(
                                run_id=run_context.run_id,
                                session_id=session_id,
                                message=msg,
                                is_final=False,
                                tool_calls=all_tool_calls,
                                tool_results=all_tool_results,
                                steps=run_steps,
                                requires_confirmation=True,
                                pending_state=pending_state,
                                duration_ms=duration_ms,
                            )
                            emit({"type": "message", "content": msg})
                            emit({"type": "done", "response": r.model_dump(mode="json")})
                            return r
                        results_start = len(all_tool_results)
                        for tc in valid_tools:
                            # Check budget before tool call
                            if run_context.tool_calls_count >= self.settings.max_tool_calls:
                                break
                            
                            run_context.record_tool_call()
                            emit({"type": "tool_call", "name": tc["name"], "arguments": tc["arguments"]})
                            if not self.settings.disable_restraints:
                                guard_result = self.tool_guardrails.check_args(
                                    tc["name"], tc["arguments"]
                                )
                                if not guard_result.allowed:
                                    continue
                            # Execute (on_stream for live logs; run_in_separate_shell so run_python opens a visible window)
                            _name = tc["name"]
                            on_stream = (lambda sn, txt, n=_name: emit({"type": "tool_output", "name": n, "stream": sn, "content": txt})) if emit else None
                            exec_result = await self.tool_executor.execute(
                                tc["name"],
                                tc["arguments"],
                                on_stream=on_stream,
                                run_in_separate_shell=getattr(self.settings, "run_python_in_separate_shell", False),
                                session_id=session_id,
                            )
                            
                            # Build observation
                            obs = self.observation_builder.build(
                                tc["name"], tc["arguments"], exec_result
                            )
                            
                            # Track tool calls and results
                            all_tool_calls.append(ToolCall(
                                id=tc["id"],
                                name=tc["name"],
                                arguments=tc["arguments"],
                            ))
                            
                            tr = ToolResult(
                                tool_call_id=tc["id"],
                                name=tc["name"],
                                content=exec_result.content if exec_result.success else str(exec_result.error),
                                success=exec_result.success,
                                duration_ms=exec_result.duration_ms,
                            )
                            all_tool_results.append(tr)
                            emit({
                                "type": "tool_result",
                                "name": tc["name"],
                                "content": tr.content,
                                "success": tr.success,
                                "duration_ms": tr.duration_ms,
                            })
                            # Add to tool results for next LLM call (tool_call_id required for API)
                            # Send actual result content so the model can use it (e.g. search results)
                            result_content = obs.raw_payload if obs.raw_payload else obs.summary
                            if result_content and len(result_content) > 12000:
                                result_content = result_content[:12000] + "\n... [truncated]"
                            tool_results_history.append({
                                "name": tc["name"],
                                "id": tc["id"],
                                "tool_call_id": tc["id"],
                                "content": result_content or obs.summary,
                                "raw": obs.raw_payload,
                            })
                            
                            # Memory write
                            if self.memory_writer:
                                self.memory_writer.consider_write(
                                    session_id, tc["name"], exec_result
                                )
                        
                        # Record this step: LLM reasoning + tool calls + tool results
                        n = len(valid_tools)
                        run_steps.append(RunStep(
                            reasoning=last_llm_response.get("content") or None,
                            tool_calls=all_tool_calls[-n:] if n else [],
                            tool_results=all_tool_results[results_start:],
                        ))
                        # Clear tool_calls so next iteration we CALL_LLM (synthesize) instead of re-executing
                        last_llm_response = {
                            "content": last_llm_response.get("content"),
                            "tool_calls": [],
                        }
                
                elif decision.action == Action.FINISH:
                    if not self.settings.disable_restraints:
                        quality_result = self.quality_checker.check(decision.final_answer)
                        if quality_result.needs_fix:
                            last_llm_response = {
                                "content": f"Quality check failed: {quality_result.reason}. Please fix.",
                                "tool_calls": [],
                            }
                            continue
                    # Final output
                    duration_ms = int((time.time() - start_time) * 1000)
                    emit({"type": "message", "content": decision.final_answer})
                    # Save to STM
                    self.stm.append(session_id, "assistant", decision.final_answer)

                    # Record completion
                    run_context.mark_completed()
                    r = AgentRunResponse(
                        run_id=run_context.run_id,
                        session_id=session_id,
                        message=decision.final_answer,
                        is_final=True,
                        tool_calls=all_tool_calls,
                        tool_results=all_tool_results,
                        steps=run_steps,
                        duration_ms=duration_ms,
                        usage={
                            "total_tokens": run_context.total_tokens_used,
                            "tool_calls": run_context.tool_calls_count,
                        },
                    )
                    emit({"type": "done", "response": r.model_dump(mode="json")})
                    return r
                
                step += 1
                
                # Safety: max iterations
                if step > 50:
                    return self._graceful_stop(
                        "Max iterations reached", run_context, start_time,
                        all_tool_calls, all_tool_results, run_steps, emit,
                    )
        
        except Exception as e:
            return self._graceful_stop(
                f"Error: {str(e)}", run_context, start_time,
                all_tool_calls, all_tool_results, run_steps, emit,
            )
        finally:
            await self.llm_client.close()

    async def execute_pending(
        self,
        session_id: str,
        run_context: RunContext,
        pending: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentRunResponse:
        """Execute pending tool calls (after user said 'confirm') and return final answer."""
        start_time = time.time()
        user_message = pending.get("user_message") or ""
        assistant_message = pending.get("assistant_message")
        tool_calls_raw = pending.get("tool_calls") or []
        tool_results_history: List[Dict] = []
        all_tool_calls: List[ToolCall] = []
        all_tool_results: List[ToolResult] = []

        try:
            for tc in tool_calls_raw:
                name = tc.get("name") or "?"
                args = tc.get("arguments") or {}
                tc_id = tc.get("id") or str(id(tc))
                if on_event:
                    on_event({"type": "tool_call", "name": name, "arguments": args})
                _n = name
                on_stream = (lambda sn, txt, n=_n: on_event({"type": "tool_output", "name": n, "stream": sn, "content": txt})) if on_event else None
                exec_result = await self.tool_executor.execute(
                    name,
                    args,
                    on_stream=on_stream,
                    run_in_separate_shell=getattr(self.settings, "run_python_in_separate_shell", False),
                    session_id=session_id,
                )
                obs = self.observation_builder.build(name, args, exec_result)
                all_tool_calls.append(ToolCall(id=tc_id, name=name, arguments=args))
                tr = ToolResult(
                    tool_call_id=tc_id,
                    name=name,
                    content=exec_result.content if exec_result.success else str(exec_result.error),
                    success=exec_result.success,
                    duration_ms=exec_result.duration_ms,
                )
                all_tool_results.append(tr)
                if on_event:
                    on_event({"type": "tool_result", "name": name, "content": tr.content, "success": tr.success, "duration_ms": tr.duration_ms})
                result_content = obs.raw_payload if obs.raw_payload else obs.summary
                if result_content and len(result_content) > 12000:
                    result_content = result_content[:12000] + "\n... [truncated]"
                tool_results_history.append({
                    "id": tc_id,
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": result_content or obs.summary,
                })
            build_user_message = "The user confirmed. Using the tool results above, provide your final answer to the user."
            messages = self.context_builder.build(
                user_message=build_user_message,
                session_id=session_id,
                run_context=run_context,
                tool_results=tool_results_history,
                last_assistant_message=assistant_message,
            )
            model = self.model_router.select_model("draft")
            response = await self.llm_client.chat_completions(
                messages=messages,
                model=model,
                tools=None,
                max_tokens=min(4000, self.settings.max_tokens_per_request),
            )
            run_context.record_tokens(response.usage.get("total_tokens", 0))
            final_content = (response.content or "").strip()
            if final_content:
                self.stm.append(session_id, "assistant", final_content)
            duration_ms = int((time.time() - start_time) * 1000)
            run_context.mark_completed()
            r = AgentRunResponse(
                run_id=run_context.run_id,
                session_id=session_id,
                message=final_content or "Done.",
                is_final=True,
                tool_calls=all_tool_calls,
                tool_results=all_tool_results,
                steps=[],
                duration_ms=duration_ms,
                usage={"total_tokens": run_context.total_tokens_used, "tool_calls": len(all_tool_calls)},
            )
            if on_event:
                on_event({"type": "message", "content": r.message})
                on_event({"type": "done", "response": r.model_dump(mode="json")})
            return r
        finally:
            await self.llm_client.close()

    def _graceful_stop(
        self,
        reason: str,
        run_context: RunContext,
        start_time: float,
        tool_calls: List[ToolCall],
        tool_results: List[ToolResult],
        run_steps: List[RunStep],
        emit: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentRunResponse:
        """Create graceful stop response."""
        duration_ms = int((time.time() - start_time) * 1000)
        message = self.graceful_stop.build_message(reason)
        run_context.mark_stopped(reason)
        r = AgentRunResponse(
            run_id=run_context.run_id,
            session_id=run_context.session_id,
            message=message,
            is_final=True,
            tool_calls=tool_calls,
            tool_results=tool_results,
            steps=run_steps,
            duration_ms=duration_ms,
            next_steps=["Try simplifying your request", "Break task into smaller steps"],
        )
        if emit:
            emit({"type": "message", "content": message})
            emit({"type": "done", "response": r.model_dump(mode="json")})
        return r
