#!/usr/bin/env python3
"""Launcher: open the agent CLI in its own CMD window (Windows)."""

import os
import subprocess
import sys


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    cli = os.path.join(root, "cli.py")
    python = sys.executable

    if sys.platform == "win32":
        # New console window on Windows
        subprocess.Popen(
            [python, cli] + sys.argv[1:],
            cwd=root,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return 0
    # On macOS/Linux, run in foreground (no separate terminal by default)
    return subprocess.call([python, cli] + sys.argv[1:], cwd=root)


if __name__ == "__main__":
    sys.exit(main())
