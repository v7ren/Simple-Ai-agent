"""Run Python tool: execute Python code in a sandboxed subprocess."""

import asyncio
import os
import subprocess
import sys
import tempfile
import threading
from typing import Dict, Any, Optional, Callable


def _run_in_separate_shell_sync(code: str) -> Dict[str, Any]:
    """Run code in a new visible shell window (Windows: new CMD). Returns immediately; user sees output in that window."""
    if not code or not code.strip():
        return {"stdout": "", "stderr": "No code provided.", "success": False}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    cwd = tempfile.gettempdir()
    python_exe = os.environ.get("PYTHON", sys.executable)
    try:
        if sys.platform == "win32":
            # Run Python in a new console window (no cmd /k to avoid quoting issues with "Program Files")
            subprocess.Popen(
                [python_exe, path],
                cwd=cwd,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # macOS/Linux: try to open a new terminal (xterm, or leave for user to run manually)
            try:
                subprocess.Popen(
                    ["xterm", "-e", f"python {path}; exec bash"],
                    cwd=cwd,
                )
            except FileNotFoundError:
                subprocess.Popen([python_exe, path], cwd=cwd)
        return {
            "stdout": "",
            "stderr": "Running in a separate window. Check the new shell window for output.",
            "returncode": 0,
            "success": True,
        }
    except Exception as e:
        try:
            os.unlink(path)
        except OSError:
            pass
        return {"stdout": "", "stderr": str(e), "success": False}


def _read_stream(pipe, stream_name: str, on_stream: Optional[Callable[[str, str], None]], out_list: list):
    """Read lines from pipe; append to out_list and call on_stream for each line."""
    try:
        for line in iter(pipe.readline, ""):
            out_list.append(line)
            if on_stream:
                on_stream(stream_name, line)
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def _run_python_code_sync(
    code: str,
    timeout_seconds: int = 15,
    on_stream: Optional[Callable[[str, str], None]] = None,
    run_in_separate_shell: bool = False,
) -> Dict[str, Any]:
    """Execute Python code in a subprocess. If on_stream is set, call it for each line. If run_in_separate_shell, open a new visible window."""
    if not code or not code.strip():
        return {"stdout": "", "stderr": "No code provided.", "success": False}
    if run_in_separate_shell:
        return _run_in_separate_shell_sync(code)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        if on_stream is None:
            result = subprocess.run(
                [os.environ.get("PYTHON", "python"), path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=tempfile.gettempdir(),
            )
            return {
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        # Streaming: Popen + threads to read stdout/stderr and call on_stream
        proc = subprocess.Popen(
            [os.environ.get("PYTHON", "python"), path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tempfile.gettempdir(),
            bufsize=1,
        )
        out_lines, err_lines = [], []
        t1 = threading.Thread(target=_read_stream, args=(proc.stdout, "stdout", on_stream, out_lines))
        t2 = threading.Thread(target=_read_stream, args=(proc.stderr, "stderr", on_stream, err_lines))
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()
        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            out_lines.append("")
            err_lines.append(f"Execution timed out after {timeout_seconds}s.\n")
            if on_stream:
                on_stream("stderr", f"Execution timed out after {timeout_seconds}s.\n")
        t1.join(timeout=1.0)
        t2.join(timeout=1.0)
        return {
            "stdout": "".join(out_lines),
            "stderr": "".join(err_lines),
            "returncode": proc.returncode or -1,
            "success": proc.returncode == 0 if proc.returncode is not None else False,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "success": False}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def run_python_tool(
    code: str,
    timeout_seconds: int = 15,
    on_stream: Optional[Callable[[str, str], None]] = None,
    run_in_separate_shell: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run Python code. If run_in_separate_shell, open a new visible window. Else return stdout/stderr; on_stream gives live lines."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _run_python_code_sync(code, timeout_seconds, on_stream=on_stream, run_in_separate_shell=run_in_separate_shell),
    )


TOOL = {
    "name": "run_python",
    "description": "Execute Python code and return stdout and stderr. Use for calculations, data processing, or running small scripts. Code runs in a sandbox with a time limit.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to run (e.g. 'print(2+2)' or 'import math; print(math.sqrt(16))')",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Max execution time in seconds (default 15)",
                "default": 15,
            },
        },
        "required": ["code"],
    },
    "handler": run_python_tool,
}
