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

See `example.env` for all available options including:
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
