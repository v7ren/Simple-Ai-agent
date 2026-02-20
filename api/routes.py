"""API routes for the agent."""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from config import Settings
from api.schemas import AgentRunRequest, AgentRunResponse, HealthResponse, RefusalResponse
from api.auth import (
    security, verify_api_key, get_client_id, AbuseChecker,
    raise_auth_error, raise_rate_limit_error, raise_abuse_error
)
from api.dependencies import get_settings_dep, set_run_context
from context.run_context import RunContext
from pipeline.input import InputNormalizer
from pipeline.policy import PolicyEngine
from pipeline.refusal import RefusalHandler
from agent_loop.loop import AgentLoop


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


@router.post("/agent/run", response_model=AgentRunResponse)
async def run_agent(
    request_data: AgentRunRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings_dep),
):
    """Run the agent with a user message."""
    
    # 1. Authentication
    if not verify_api_key(credentials, settings):
        raise_auth_error()
    
    # 2. Rate limiting and abuse checks (skipped if restraints disabled)
    if not settings.disable_restraints:
        client_id = get_client_id(request)
        abuse_checker = AbuseChecker(settings)
        abuse_error = abuse_checker.check(request_data.message, client_id)
        if abuse_error:
            raise_abuse_error(abuse_error)
    
    # 3. Generate session ID if not provided
    session_id = request_data.session_id or str(uuid.uuid4())
    
    # 4. Create run context
    run_context = RunContext(
        session_id=session_id,
        max_time_seconds=settings.max_time_seconds,
        max_tool_calls=settings.max_tool_calls,
        max_tokens_per_request=settings.max_tokens_per_request,
        max_cost_per_request=settings.max_cost_per_request,
    )
    set_run_context(request, run_context)
    
    # 5. Input normalization
    normalizer = InputNormalizer()
    normalized_input = normalizer.normalize(request_data.message, run_context, request_data.metadata)
    
    # 6. Policy and safety check (skipped if restraints disabled)
    if not settings.disable_restraints:
        policy_engine = PolicyEngine(settings)
        policy_result = policy_engine.check(normalized_input)
        if not policy_result.allowed:
            refusal_handler = RefusalHandler()
            refusal_response = refusal_handler.create_response(
                reason=policy_result.reason,
                alternative=policy_result.alternative,
                run_context=run_context,
            )
            return AgentRunResponse(
                run_id=run_context.run_id,
                session_id=session_id,
                message=refusal_response.message,
                is_final=True,
                duration_ms=0,
            )
    
    # 7. If user said "confirm" and we have pending tool execution for this session, run it and return
    pending_store = getattr(request.app.state, "pending_confirm", None)
    if pending_store is not None and normalized_input.content.strip().lower() == "confirm":
        pending = pending_store.pop(session_id, None)
        if pending is not None:
            stm = getattr(request.app.state, "stm", None)
            agent_loop = AgentLoop(settings, stm=stm)
            response = await agent_loop.execute_pending(
                session_id=session_id,
                run_context=run_context,
                pending=pending,
            )
            return response
    
    # 8. Execute agent loop (use shared STM so conversation history persists across requests)
    stm = getattr(request.app.state, "stm", None)
    agent_loop = AgentLoop(settings, stm=stm)
    response = await agent_loop.run(
        user_message=normalized_input.content,
        session_id=session_id,
        run_context=run_context,
    )
    if getattr(response, "requires_confirmation", False) and getattr(response, "pending_state", None):
        pending_store = getattr(request.app.state, "pending_confirm", None)
        if pending_store is not None:
            pending_store[session_id] = response.pending_state
    return response


@router.post("/agent/run/stream")
async def run_agent_stream(
    request_data: AgentRunRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings_dep),
):
    """Run the agent and stream progress events (reasoning, tool_call, tool_result, message, done) as SSE."""
    if not verify_api_key(credentials, settings):
        raise_auth_error()
    if not settings.disable_restraints:
        client_id = get_client_id(request)
        abuse_checker = AbuseChecker(settings)
        abuse_error = abuse_checker.check(request_data.message, client_id)
        if abuse_error:
            raise_abuse_error(abuse_error)

    session_id = request_data.session_id or str(uuid.uuid4())
    run_context = RunContext(
        session_id=session_id,
        max_time_seconds=settings.max_time_seconds,
        max_tool_calls=settings.max_tool_calls,
        max_tokens_per_request=settings.max_tokens_per_request,
        max_cost_per_request=settings.max_cost_per_request,
    )
    set_run_context(request, run_context)

    normalizer = InputNormalizer()
    normalized_input = normalizer.normalize(request_data.message, run_context, request_data.metadata)
    if not settings.disable_restraints:
        policy_engine = PolicyEngine(settings)
        policy_result = policy_engine.check(normalized_input)
        if not policy_result.allowed:
            refusal_handler = RefusalHandler()
            refusal_response = refusal_handler.create_response(
                reason=policy_result.reason,
                alternative=policy_result.alternative,
                run_context=run_context,
            )
            payload = {
                "type": "done",
                "response": {
                    "run_id": run_context.run_id,
                    "session_id": session_id,
                    "message": refusal_response.message,
                    "is_final": True,
                    "duration_ms": 0,
                },
            }
            async def one_event():
                yield f"data: {json.dumps(payload)}\n\n"
            return StreamingResponse(one_event(), media_type="text/event-stream")

    # Handle "confirm" for pending tool execution (stream path)
    pending_store = getattr(request.app.state, "pending_confirm", None)
    if pending_store is not None and normalized_input.content.strip().lower() == "confirm":
        pending = pending_store.pop(session_id, None)
        if pending is not None:
            async def confirm_stream():
                stm = getattr(request.app.state, "stm", None)
                agent_loop = AgentLoop(settings, stm=stm)
                r = await agent_loop.execute_pending(
                    session_id=session_id,
                    run_context=run_context,
                    pending=pending,
                )
                yield f"data: {json.dumps({'type': 'done', 'response': r.model_dump(mode='json')})}\n\n"
            return StreamingResponse(confirm_stream(), media_type="text/event-stream")

    pending_store = getattr(request.app.state, "pending_confirm", None)
    event_queue: asyncio.Queue = asyncio.Queue()

    def on_event(ev: dict) -> None:
        event_queue.put_nowait(ev)

    async def event_stream():
        stm = getattr(request.app.state, "stm", None)
        agent_loop = AgentLoop(settings, stm=stm)
        task = asyncio.create_task(
            agent_loop.run(
                user_message=normalized_input.content,
                session_id=session_id,
                run_context=run_context,
                on_event=on_event,
            )
        )
        try:
            while True:
                ev = await event_queue.get()
                yield f"data: {json.dumps(ev)}\n\n"
                if ev.get("type") == "done":
                    resp = ev.get("response") or {}
                    if resp.get("requires_confirmation") and resp.get("pending_state") and pending_store is not None:
                        pending_store[session_id] = resp["pending_state"]
                    break
        finally:
            await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/agent/status/{run_id}")
async def get_run_status(
    run_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings_dep),
):
    """Get status of a specific run."""
    if not verify_api_key(credentials, settings):
        raise_auth_error()
    
    # TODO: Implement status tracking
    return {"run_id": run_id, "status": "unknown"}
