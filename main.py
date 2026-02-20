"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import router
from api.auth import limiter
from config import get_settings
from context.stm import ShortTermMemory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    settings = get_settings()
    app.state.stm = ShortTermMemory(max_turns=settings.stm_max_turns)
    app.state.pending_confirm = {}  # session_id -> pending tool run (for require_user_confirm)
    print(f"Starting {settings.agent_name} on Python 3.11+")
    print(f"Agent mode: {settings.agent_mode} (restrained = policy/guardrails on, no confirm; free = no restraints, confirm before tools)")
    print(f"Run Python in separate shell: {getattr(settings, 'run_python_in_separate_shell', True)} (new CMD window when agent runs code)")
    print(f"Default model: {settings.openrouter_default_model}")
    print(f"LTM enabled: {settings.ltm_enabled}")
    print(f"Retrieval enabled: {settings.retrieval_enabled}")
    
    yield
    
    # Shutdown
    print("Shutting down...")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    
    app = FastAPI(
        title="AI Agent",
        description="AI agent with OpenRouter integration",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Add rate limiter
    app.state.limiter = limiter
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routes
    app.include_router(router, prefix="/api/v1")
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
