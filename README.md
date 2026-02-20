# AI Agent

An AI agent built with FastAPI, OpenRouter, and modular components following the architecture from `architecture.md` and behavior from `skill.md`.

## Features

- **API Gateway**: FastAPI with auth, rate limiting, and abuse checks
- **Pipeline**: Input normalization, policy guardrails, refusal handling
- **Memory**: Short-term (in-memory), Long-term (SQLite), Retrieval
- **LLM**: OpenRouter client with model routing and prompt composition
- **Tools**: Registry, selector, guardrails, executor, observation builder
- **Agent Loop**: Decide module with budget tracking and graceful stop
- **Quality**: Safety checks and output validation

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp example.env .env
# Edit .env with your OpenRouter API key
```

3. Run the server:
```bash
python main.py
```

4. Test the agent:
```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, agent!"}'
```

## API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/agent/run` - Run the agent

## Project Structure

```
agent/
├── main.py              # FastAPI app
├── config.py            # Settings
├── api/                 # API layer
├── pipeline/            # Input/policy
├── context/             # Memory (STM/LTM)
├── llm/                 # OpenRouter client
├── tools/               # Tool registry
├── agent_loop/          # Main loop
├── prompts/             # System prompts
└── requirements.txt
```

## Configuration

See below for all available options including:
this is an example of the .env
```
# Example environment configuration for AI Agent
# Copy this to .env and fill in your values

# Required: OpenRouter configuration
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Optional: Model selection
OPENROUTER_DEFAULT_MODEL=openai/gpt-4o-mini
OPENROUTER_VERIFICATION_MODEL=anthropic/claude-3.5-sonnet

# Required: Agent configuration
AGENT_NAME=MyAgent
AGENT_DESCRIPTION=An AI agent that helps users achieve goals

# Optional: Budget limits (search + answer needs ~20k+ tokens; raise if you hit "Budget exhausted")
MAX_TOOL_CALLS=15
MAX_TIME_SECONDS=180
MAX_TOKENS_PER_REQUEST=64000
MAX_COST_PER_REQUEST=5.0

# Optional: Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Optional: Memory configuration
LTM_ENABLED=false
RETRIEVAL_ENABLED=false
RETRIEVAL_TOP_K=5
STM_MAX_TURNS=20

# Optional: Security
API_KEY=optional_api_key_for_auth
JWT_SECRET=optional_jwt_secret
MAX_INPUT_LENGTH=10000

# Optional: Run Python in a separate shell window (default true). When true, run_python opens a new CMD window so you see output there.
# RUN_PYTHON_IN_SEPARATE_SHELL=true

# Optional: Feature flags
# All tools: use * or leave empty. Or list: ALLOWED_TOOLS=echo,search,run_python
ALLOWED_TOOLS=*

```
- OpenRouter API settings
- Model selection (draft/verification)
- Budget limits (tokens, time, cost)
- Memory and retrieval settings
- Security options

## Architecture

The agent follows the flow from `architecture.md`:
```
Gateway → Auth → Input Normalizer → Policy → Context Builder → Agent Loop
                                           ↓
         STM ← Context ←→ LTM ← Retrieval
                                           ↓
                        Decide → LLM ↔ Tool Execution → Finish
```

## License

MIT
