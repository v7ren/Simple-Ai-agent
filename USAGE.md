# How to Use the AI Agent

## 1. Install

From the project root (`agent/`):

```bash
pip install -r requirements.txt
```

## 2. Configure

Create a `.env` file (copy from `example.env`):

**Windows (PowerShell):**
```powershell
Copy-Item example.env .env
```

**macOS/Linux:**
```bash
cp example.env .env
```

**Required:** Set your OpenRouter API key in `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
```

Get a key at [OpenRouter](https://openrouter.ai/).

**Optional:** Adjust in `.env`:
- `AGENT_NAME` – name shown in system prompt
- `OPENROUTER_DEFAULT_MODEL` – e.g. `openai/gpt-4o-mini`
- `MAX_TOOL_CALLS`, `MAX_TIME_SECONDS` – limits per request
- `API_KEY` – if set, requests must send `Authorization: Bearer <API_KEY>`

## 3. Run the server

```bash
python main.py
```

Server runs at **http://localhost:8000**.

Check health:
```bash
curl http://localhost:8000/api/v1/health
```

## 4. Use the CLI (easiest)

With the server running, open a **second terminal** and use the CLI:

**Interactive chat** (type messages, press Enter; `/quit` or Ctrl+C to exit):
```bash
python cli.py
```

**Single message:**
```bash
python cli.py "What can you do?"
```

**Options:**
- `-v` / `--verbose` — show tool calls and duration
- `-s` / `--session ID` — use a session ID for multi-turn
- `-k` / `--api-key KEY` — API key (or set `API_KEY` in env)
- `-b` / `--base-url URL` — agent URL (default: http://localhost:8000/api/v1)

Example:
```bash
python cli.py -v "Explain recursion in one sentence"
```

## 5. Call the agent (API)

### Request

**Endpoint:** `POST /api/v1/agent/run`

**Body (JSON):**
```json
{
  "message": "Your question or task here",
  "session_id": "optional-session-id-for-conversation",
  "metadata": {}
}
```

- `message` (required) – user message.
- `session_id` (optional) – same ID across requests for conversation continuity (STM).
- `metadata` (optional) – extra data attached to the run.

If you set `API_KEY` in `.env`, add the header:
```
Authorization: Bearer your_api_key
```

### Examples

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agent/run" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"message": "Hello, what can you do?"}'
```

**curl:**
```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hello, what can you do?\"}"
```

**Python:**
```python
import requests

resp = requests.post(
    "http://localhost:8000/api/v1/agent/run",
    json={"message": "Hello, what can you do?"},
)
data = resp.json()
print(data["message"])
```

### Response

```json
{
  "run_id": "uuid",
  "session_id": "uuid-or-your-session-id",
  "message": "The agent's reply text",
  "is_final": true,
  "tool_calls": [],
  "tool_results": [],
  "usage": { "total_tokens": 123, "tool_calls": 0 },
  "duration_ms": 1500,
  "timestamp": "2025-02-20T...",
  "next_steps": []
}
```

- `message` – main reply (or refusal/graceful-stop message).
- `is_final` – `true` when the agent is done; `false` when it’s asking a clarifying question.
- `tool_calls` / `tool_results` – tools used and their results.
- `next_steps` – suggestions (e.g. after graceful stop).

## 7. Multi-turn conversation

Use the same `session_id` for follow-up messages:

```json
{"message": "Remember my name is Alice", "session_id": "conv-001"}
{"message": "What's my name?", "session_id": "conv-001"}
```

Short-term memory keeps the last N turns per session (see `STM_MAX_TURNS` in `.env`).

## 8. Optional: long-term memory

In `.env` set:

```
LTM_ENABLED=true
RETRIEVAL_ENABLED=true
```

The agent can then store and retrieve facts/preferences per session (SQLite DB `agent_ltm.db` is created automatically).

## 9. Troubleshooting

| Issue | Fix |
|-------|-----|
| `Invalid or missing API key` | Set `API_KEY` in `.env` or send `Authorization: Bearer <key>`; if you don’t want auth, leave `API_KEY` unset. |
| `OPENROUTER_API_KEY` error | Ensure `.env` has a valid key and the app loads it (run from the `agent/` directory). |
| Empty or slow replies | Check OpenRouter status; try a different `OPENROUTER_DEFAULT_MODEL` (e.g. `openai/gpt-4o-mini`). |
| Request blocked | Input may hit policy/abuse checks (length, blocked keywords); simplify or shorten the message. |

## 10. API docs

With the server running:

- **Swagger UI:** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  

You can try `POST /api/v1/agent/run` from the browser there.
