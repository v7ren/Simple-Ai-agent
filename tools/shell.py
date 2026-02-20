"""Shell tools: open a shell, run commands in it, close it."""

import asyncio
import os
import subprocess
import sys
import threading
import time
from typing import Dict, Any, Optional

# Session -> process (so agent can have one shell per session or shared)
_shells: Dict[str, subprocess.Popen] = {}
_lock = threading.Lock()

# Prompt we inject so we know when command output is done
_END_MARKER = "AGENTSHELL_END"


def _get_proc(session_id: str) -> Optional[subprocess.Popen]:
    with _lock:
        return _shells.get(session_id)


def _set_proc(session_id: str, proc: Optional[subprocess.Popen]) -> None:
    with _lock:
        if proc is None:
            _shells.pop(session_id, None)
        else:
            _shells[session_id] = proc


def _open_shell_sync(session_id: str) -> Dict[str, Any]:
    """Start a persistent shell process (cmd on Windows, sh on Unix)."""
    with _lock:
        if session_id in _shells:
            try:
                _shells[session_id].poll()
                if _shells[session_id].returncode is None:
                    return {"success": True, "message": "Shell already open for this session."}
            except Exception:
                pass
            try:
                _shells[session_id].terminate()
            except Exception:
                pass
            _shells.pop(session_id, None)
    try:
        if sys.platform == "win32":
            # /q = no echo of batch, /k = keep open; set prompt so we can detect when command output is done
            proc = subprocess.Popen(
                ["cmd", "/q", "/k", "prompt", _END_MARKER + "_"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd(),
            )
        else:
            proc = subprocess.Popen(
                ["sh", "-i"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd(),
                env={**os.environ, "PS1": _END_MARKER},
            )
        _set_proc(session_id, proc)
        return {"success": True, "message": "Shell opened. Use run_shell_command to run commands, close_shell to close it."}
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": str(e)}


def _run_command_sync(session_id: str, command: str, timeout_seconds: float = 10.0) -> Dict[str, Any]:
    """Send command to the shell and read output until we see the end marker or timeout."""
    proc = _get_proc(session_id)
    if proc is None:
        return {"success": False, "error": "No shell open. Call open_shell first.", "stdout": "", "stderr": ""}
    try:
        if proc.poll() is not None:
            _set_proc(session_id, None)
            return {"success": False, "error": "Shell process has exited. Call open_shell again.", "stdout": "", "stderr": ""}
        proc.stdin.write(command.strip() + "\n")
        proc.stdin.flush()
    except Exception as e:
        _set_proc(session_id, None)
        return {"success": False, "error": str(e), "stdout": "", "stderr": str(e)}
    out_lines = []
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            if _END_MARKER in line:
                break  # do not include the prompt line in output
            out_lines.append(line)
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "".join(out_lines), "stderr": str(e)}
    out = "".join(out_lines)
    return {"success": True, "stdout": out, "stderr": "", "command": command}


def _close_shell_sync(session_id: str) -> Dict[str, Any]:
    """Kill the shell process for this session."""
    proc = _get_proc(session_id)
    if proc is None:
        return {"success": True, "message": "No shell was open."}
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    except Exception:
        pass
    _set_proc(session_id, None)
    return {"success": True, "message": "Shell closed."}


async def open_shell_tool(
    session_id: str = "_default",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Open a persistent shell for this session. Use run_shell_command to run commands in it."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _open_shell_sync(session_id))


async def run_shell_command_tool(
    command: str,
    session_id: str = "_default",
    timeout_seconds: float = 10.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run a command in the open shell. Open a shell first with open_shell if needed."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _run_command_sync(session_id, command, timeout_seconds),
    )


async def close_shell_tool(
    session_id: str = "_default",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Close the shell for this session."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _close_shell_sync(session_id))


TOOL_OPEN = {
    "name": "open_shell",
    "description": "Open a persistent shell (CMD on Windows, sh on Unix). Use run_shell_command to run commands in it, close_shell to close it.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "handler": open_shell_tool,
}

TOOL_RUN = {
    "name": "run_shell_command",
    "description": "Run a command in the open shell. Call open_shell first if you have not. Supports any shell command (dir, cd, python, etc.).",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to run (e.g. 'dir', 'cd C:\\temp', 'python script.py')",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Max seconds to wait for output (default 10)",
                "default": 10,
            },
        },
        "required": ["command"],
    },
    "handler": run_shell_command_tool,
}

TOOL_CLOSE = {
    "name": "close_shell",
    "description": "Close the persistent shell for this session.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "handler": close_shell_tool,
}


def _open_shell_window_sync() -> Dict[str, Any]:
    """Open a visible CMD/shell window (user can type there; not controlled by the agent)."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/k"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            try:
                subprocess.Popen(["xterm", "-e", "sh"], cwd=os.getcwd())
            except FileNotFoundError:
                subprocess.Popen(["gnome-terminal", "--", "sh"], cwd=os.getcwd())
        return {"success": True, "message": "A new shell window was opened. You can use it yourself; the agent uses open_shell/run_shell_command for its own shell."}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def open_shell_window_tool(**kwargs: Any) -> Dict[str, Any]:
    """Open a visible shell window on the user's screen (for the user to type in). The agent uses open_shell + run_shell_command for running commands."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _open_shell_window_sync)


TOOL_OPEN_WINDOW = {
    "name": "open_shell_window",
    "description": "Open a new visible CMD/shell window on the user's screen. The user can type in it. For the agent to run commands, use open_shell then run_shell_command instead.",
    "parameters": {"type": "object", "properties": {}, "required": []},
    "handler": open_shell_window_tool,
}


def _stop_server_sync(port: int) -> Dict[str, Any]:
    """Kill the process listening on the given port (e.g. 5000 for Flask). Does NOT use the persistent shell."""
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pids = set()
            for line in (r.stdout or "").splitlines():
                if "LISTENING" not in line or f":{port}" not in line:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[-1].isdigit():
                    pids.add(parts[-1])
            if not pids:
                return {"success": False, "error": f"No process found listening on port {port}.", "port": port}
            for pid in pids:
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=3)
                except Exception:
                    pass
            return {"success": True, "message": f"Stopped process(es) on port {port}.", "port": port}
        else:
            r = subprocess.run(
                ["sh", "-c", f"lsof -ti :{port} | xargs -r kill -9 2>/dev/null; exit 0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return {"success": True, "message": f"Stopped process(es) on port {port}.", "port": port}
    except Exception as e:
        return {"success": False, "error": str(e), "port": port}


async def stop_server_tool(port: int = 5000, **kwargs: Any) -> Dict[str, Any]:
    """Stop a server (e.g. Flask) running on the given port by killing the process listening on it. Use this when the user says 'close the server' or 'stop the Flask app' — not close_shell (which only closes the agent's shell)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _stop_server_sync(port))


TOOL_STOP_SERVER = {
    "name": "stop_server",
    "description": "Stop a server running on a port (e.g. Flask on 5000). Kills the process listening on that port. Use when the user says 'close the server' or 'stop the Flask app'. Do NOT use close_shell for that — close_shell only closes the agent's persistent shell, not servers started by run_python or in other windows.",
    "parameters": {
        "type": "object",
        "properties": {
            "port": {
                "type": "integer",
                "description": "Port number (default 5000 for Flask)",
                "default": 5000,
            },
        },
        "required": [],
    },
    "handler": stop_server_tool,
}
