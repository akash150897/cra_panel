#!/usr/bin/env python3
"""Code Review Agent — entry point.

This file is the single CLI entry point for all agent operations and
is also the script called by the installed git pre-push hook.
"""

import sys
from pathlib import Path

# Ensure the project root is on the path when executed directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.cli import run_cli  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_cli())
