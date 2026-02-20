# Tools reference (for the LLM)

Use these tools when they help answer the user. Call them by **name** with the correct **arguments** (JSON). Prefer the minimum number of tool calls needed.

---

## echo

**When to use:** Testing or echoing back a user message. Not for real tasks.

**Arguments:**

| Argument   | Type   | Required | Description      |
|-----------|--------|----------|------------------|
| `message` | string | yes      | Message to echo. |

**Returns:** `{ "echo": "<message>", "timestamp": "..." }`

**Example:** `echo(message="Hello")` → use when the user asks to repeat or test.

---

## search

**When to use:** Current events, facts, documentation, or anything that needs up-to-date or external information. Use a clear, short query.

**Arguments:**

| Argument       | Type    | Required | Description                          |
|----------------|---------|----------|--------------------------------------|
| `query`        | string  | yes      | Search query (e.g. "date today", "Python asyncio"). |
| `max_results` | integer | no       | Max results to return (default 5).    |

**Returns:** `{ "query": "...", "results": [ { "title", "url", "snippet" }, ... ], "total": N }`. Use `results[].snippet` and `title`/`url` to answer. If `error` is present, report the hint (e.g. install `duckduckgo-search`).

**Example:** For "what's the date today?" → `search(query="current date today")` then summarize the first result.

---

## run_python

**When to use:** Math, small calculations, data processing, **or running a single script/server** (e.g. a Flask app, a one-off script). Prefer this when the user says "write and run" or "run this" for one block of code — it runs in a separate window and the user sees output there. Code runs with a time limit; for servers, the window stays open while the server runs.

**Arguments:**

| Argument          | Type    | Required | Description                                |
|-------------------|---------|----------|--------------------------------------------|
| `code`            | string  | yes      | Python code (e.g. `print(2+2)` or a small script). |
| `timeout_seconds` | integer | no       | Max execution time in seconds (default 15). |

**Returns:** `{ "stdout": "...", "stderr": "...", "returncode": N, "success": true/false }`. Prefer `stdout` for the answer; use `stderr` only if there was an error.

**Examples:**  
- "what is 15 * 27?" → `run_python(code="print(15 * 27)")`.  
- "write a Flask server and run it" → use **run_python** with the full Flask code (one call). Do **not** use open_shell for this; run_python opens its own window and runs the script.

**Guidelines:**  
- For "write and run" a server or single script: use **run_python** with the complete code so it actually runs.  
- Keep code short and safe when possible.  
- No `open()` outside temp, no network, no `os.system`/`subprocess` in the code.  
- Prefer a single expression or a few lines for calculations; full scripts are fine for servers.

---

## open_shell

**When to use:** The user needs a **persistent** shell so you can run **multiple separate commands** (e.g. `cd C:\projects` then `dir`, or a sequence of shell commands). Do **not** use open_shell for "write and run this script/server" — use **run_python** instead so the code actually runs in one go.

**Arguments:** None.

**Returns:** `{ "success": true, "message": "..." }` or `{ "success": false, "error": "..." }`. Call `run_shell_command` next to run commands; call `close_shell` when done.

**Example:** User says "open a shell and list my Desktop" → `open_shell()` then `run_shell_command(command="dir %USERPROFILE%\\Desktop")` (Windows) or `run_shell_command(command="ls ~/Desktop")` (Unix).

---

## run_shell_command

**When to use:** Run a command in the shell that was opened with `open_shell`. Use for `dir`, `cd`, `python script.py`, `git status`, etc.

**Arguments:**

| Argument           | Type   | Required | Description                                      |
|--------------------|--------|----------|--------------------------------------------------|
| `command`          | string | yes      | The shell command (e.g. `dir`, `cd C:\temp`).   |
| `timeout_seconds`  | number | no       | Max seconds to wait for output (default 10).     |

**Returns:** `{ "success": true, "stdout": "...", "stderr": "", "command": "..." }` or `{ "success": false, "error": "..." }`. If no shell is open, call `open_shell` first.

---

## close_shell

**When to use:** Close the **persistent shell** (the one opened with `open_shell`) for this session. **This does NOT stop servers** (e.g. Flask) that are running in another window or started by `run_python`. For "close the server" or "stop the Flask app", use **stop_server** instead.

**Arguments:** None.

**Returns:** `{ "success": true, "message": "Shell closed." }`

---

## stop_server

**When to use:** The user says "close the server", "stop the Flask app", or "stop what's running on port 5000". This kills the process listening on the given port. Use this — **not** close_shell — to actually stop a Flask or other server that is running in a separate window or from run_python.

**Arguments:**

| Argument | Type    | Required | Description                    |
|----------|---------|----------|--------------------------------|
| `port`   | integer | no       | Port number (default 5000).   |

**Returns:** `{ "success": true, "message": "Stopped process(es) on port 5000.", "port": 5000 }` or `{ "success": false, "error": "..." }`.

**Example:** User says "now close it" (after a Flask server is running) → `stop_server(port=5000)`.

---

## open_shell_window

**When to use:** Open a new visible CMD/shell window on the user's screen so they can type in it themselves. The agent does not run commands in that window; use `open_shell` + `run_shell_command` for the agent to run commands.

**Arguments:** None.

**Returns:** `{ "success": true, "message": "..." }`

---

## General rules

1. **Choose the right tool:** Use `search` for real-time or external info, `run_python` for computation, `open_shell`/`run_shell_command` for shell commands, `stop_server` to stop a server on a port, `open_shell_window` to open a visible window, `echo` only for tests.
2. **Stopping a server:** When the user says "close the server" or "stop the Flask app", use **stop_server(port=5000)**. Do not use close_shell — that only closes the agent's shell, not the server process.
3. **Shell flow:** Open a shell with `open_shell`, run commands with `run_shell_command`, close with `close_shell` when done.
4. **One task, few calls:** Prefer one search or one run_python when enough; avoid redundant calls.
5. **Use results:** Always base your answer on the tool’s return value; don’t invent outputs.
6. **Errors:** If a tool returns an `error` or `success: false`, say so and suggest a fix (e.g. install a package) when relevant.
