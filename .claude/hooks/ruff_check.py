"""PostToolUse hook: lint a Python file Claude just edited.

Reads the hook payload on stdin, and if the edited file is Python, runs
``ruff check`` on it. Findings go to stderr with exit code 2, which is how a
PostToolUse hook feeds them back to Claude so they get fixed in the same turn.

Deliberately silent (exit 0) when the edit was not Python, when the payload has
no path, or when ruff is not installed — a missing dev dependency should not
turn every edit into an error.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

# Ruff normally ignores paths it was told to exclude only when discovering files
# itself; --force-exclude makes it honour extend-exclude for an explicit path too,
# so editing third_party/ or .claude/ does not get linted against project rules.
RUFF_ARGS = ["check", "--force-exclude", "--output-format", "concise"]


def _edited_path(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    return str(
        tool_input.get("file_path")
        or tool_response.get("filePath")
        or ""
    ).strip()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = _edited_path(payload)
    if not path.endswith(".py"):
        return 0

    ruff = shutil.which("ruff")
    if ruff is None:
        return 0

    result = subprocess.run(
        [ruff, *RUFF_ARGS, path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return 0

    findings = (result.stdout + result.stderr).strip()
    if not findings:
        return 0
    print(f"ruff check failed for {path}:\n{findings}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
