#!/usr/bin/env python3
"""CLI to chat with the AI agent (server must be running)."""

import argparse
import json
import os
import sys
import time
import uuid

# Load .env so API_KEY (and AGENT_BASE_URL) are available when talking to the server
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx


DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


def run_one(
    message: str,
    base_url: str,
    api_key: str | None,
    session_id: str | None,
) -> dict:
    """Send one message and return the response JSON."""
    url = f"{base_url.rstrip('/')}/agent/run"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def run_one_live(
    message: str,
    base_url: str,
    api_key: str | None,
    session_id: str | None,
) -> dict | None:
    """Send one message, stream progress events (thinking, tool use, code, output), return final response or None."""
    url = f"{base_url.rstrip('/')}/agent/run/stream"
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    final_response = None
    # Long read timeout for SSE: server may be idle while calling LLM (minutes between events)
    stream_timeout = httpx.Timeout(30.0, read=600.0)
    with httpx.Client(timeout=stream_timeout) as client:
        with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            buf = ""
            for chunk in resp.iter_text():
                buf += chunk
                while "\n\n" in buf:
                    part, buf = buf.split("\n\n", 1)
                    for line in part.splitlines():
                        if line.startswith("data: "):
                            try:
                                ev = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue
                            t = ev.get("type")
                            if t == "reasoning":
                                c = (ev.get("content") or "").strip()
                                if c:
                                    print("\nThinking:", c)
                            elif t == "tool_call":
                                name = ev.get("name", "?")
                                args = ev.get("arguments") or {}
                                if name == "run_python" and "code" in args:
                                    print("\nCode:")
                                    print(args["code"])
                                    print("---")
                                else:
                                    print("\nTool:", name, json.dumps(args))
                            elif t == "tool_output":
                                stream = ev.get("stream", "out")
                                content = ev.get("content", "")
                                if content:
                                    prefix = "[stdout] " if stream == "stdout" else "[stderr] "
                                    sys.stdout.write(prefix + content)
                                    sys.stdout.flush()
                            elif t == "tool_result":
                                name = ev.get("name", "?")
                                content = ev.get("content", "")
                                success = ev.get("success", True)
                                status = "ok" if success else "failed"
                                print(f"\n→ {name} [{status}]:")
                                print(content if content else "(no output)")
                            elif t == "message":
                                c = (ev.get("content") or "").strip()
                                if c:
                                    print("\nAgent:", c)
                            elif t == "done":
                                final_response = ev.get("response")
                                if final_response and final_response.get("duration_ms") is not None:
                                    print(f"\n[{final_response['duration_ms']} ms]")
                if buf.strip().startswith("data:"):
                    try:
                        ev = json.loads(buf.strip()[5:].strip())
                        if ev.get("type") == "done":
                            final_response = ev.get("response")
                    except json.JSONDecodeError:
                        pass
    return final_response


def _print_steps(steps: list) -> None:
    """Print each run step: LLM reasoning, tool calls, and tool results."""
    for i, step in enumerate(steps, 1):
        if isinstance(step, dict):
            reasoning = step.get("reasoning")
            tool_calls = step.get("tool_calls", [])
            tool_results = step.get("tool_results", [])
        else:
            reasoning = getattr(step, "reasoning", None)
            tool_calls = getattr(step, "tool_calls", []) or []
            tool_results = getattr(step, "tool_results", []) or []
        print(f"\n--- Step {i} ---")
        if reasoning and reasoning.strip():
            print("Thinking:", reasoning.strip())
        for tc in tool_calls:
            name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
            args = tc.get("arguments", {}) if isinstance(tc, dict) else getattr(tc, "arguments", {})
            args_str = json.dumps(args) if args else "{}"
            print(f"  Tool: {name}({args_str})")
        for tr in tool_results:
            name = tr.get("name", "?") if isinstance(tr, dict) else getattr(tr, "name", "?")
            content = tr.get("content", "") if isinstance(tr, dict) else getattr(tr, "content", "")
            success = tr.get("success", True) if isinstance(tr, dict) else getattr(tr, "success", True)
            status = "ok" if success else "failed"
            preview = (content[:500] + "..." if len(content) > 500 else content) if content else "(no output)"
            print(f"  → {name} [{status}]: {preview}")


def print_response(data: dict, verbose: bool, stream: bool = False, delay: float = 0.02) -> None:
    """Print agent response to stdout. If stream=True, print letter by letter."""
    msg = data.get("message", "")
    if stream and msg:
        for ch in msg:
            sys.stdout.write(ch)
            sys.stdout.flush()
            time.sleep(delay)
        print()
    else:
        print(msg)
    steps = data.get("steps") or []
    if steps:
        _print_steps(steps)
    if verbose:
        if data.get("tool_calls") and not steps:
            print("\n[Tools used:", ", ".join(t.get("name", "?") for t in data["tool_calls"]), "]")
        if data.get("duration_ms") is not None:
            print(f"\n[{data['duration_ms']} ms]")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chat with the AI agent. Start the server first (python main.py).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive chat (default)
  python cli.py

  # One message
  python cli.py "What is 2+2?"

  # With API key and custom URL
  python cli.py --api-key xxx --base-url http://localhost:8000/api/v1
  python cli.py -v "Hello"
  python cli.py --live "What is 2+2?"   # stream progress (thinking, code, tool output)
        """,
    )
    parser.add_argument(
        "-l", "--live",
        action="store_true",
        help="Stream progress: show thinking, tool/code use, and output as they happen",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Single message to send (omit for interactive mode)",
    )
    parser.add_argument(
        "-b", "--base-url",
        default=os.environ.get("AGENT_BASE_URL", DEFAULT_BASE_URL),
        help="Agent API base URL (default: AGENT_BASE_URL or %(default)s)",
    )
    parser.add_argument(
        "-k", "--api-key",
        default=os.environ.get("API_KEY"),
        help="Optional API key (default: API_KEY env)",
    )
    parser.add_argument(
        "-s", "--session",
        default=None,
        help="Session ID for multi-turn (default: new UUID per run)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show tool calls and duration",
    )
    parser.add_argument(
        "-S", "--stream",
        action="store_true",
        dest="stream",
        default=True,
        help="Print agent reply letter by letter (default: on)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_false",
        dest="stream",
        help="Disable letter-by-letter streaming",
    )
    parser.add_argument(
        "--stream-delay",
        type=float,
        default=0.02,
        metavar="SEC",
        help="Delay per character when streaming (default: 0.02)",
    )
    args = parser.parse_args()

    session_id = args.session or str(uuid.uuid4())

    if args.message:
        # One-shot
        try:
            if args.live:
                run_one_live(args.message, args.base_url, args.api_key, session_id)
            else:
                data = run_one(args.message, args.base_url, args.api_key, session_id)
                print_response(data, args.verbose, stream=args.stream, delay=args.stream_delay)
        except httpx.HTTPStatusError as e:
            print(f"Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            return 1
        except httpx.ConnectError as e:
            print(f"Cannot connect to agent. Is the server running? ({e})", file=sys.stderr)
            return 1
        return 0

    # Interactive
    print("Agent CLI — type a message and press Enter. /quit or /exit to stop.\n")
    try:
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() in ("/quit", "/exit", "/q"):
                break
            try:
                if args.live:
                    run_one_live(line, args.base_url, args.api_key, session_id)
                else:
                    data = run_one(line, args.base_url, args.api_key, session_id)
                    print("Agent:", end=" ")
                    print_response(data, args.verbose, stream=args.stream, delay=args.stream_delay)
            except httpx.HTTPStatusError as e:
                print(f"Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            except httpx.ConnectError as e:
                print("Cannot connect to agent. Is the server running?", file=sys.stderr)
                break
            print()
    except KeyboardInterrupt:
        pass
    print("Bye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
