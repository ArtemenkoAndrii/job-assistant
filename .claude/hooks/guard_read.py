#!/usr/bin/env python3
"""PreToolUse hook for Read/Grep/Glob: keeps the agent's tools out of credential folders.

The gh token in ~/.config/gh must stay readable for `gh` inside the sandbox, so it
cannot be a Read deny rule (the sandbox applies those to every command). This hook
blocks the agent's own file tools instead. Exit code 2 blocks the call.
"""
import json
import re
import sys

BLOCKED = re.compile(r"(^|[/\\])\.config[/\\]gh([/\\]|$)")


def check(tool_input):
    """Return a reason string if the call must be blocked, else None."""
    for key in ("file_path", "path", "pattern", "glob"):
        value = str(tool_input.get(key) or "")
        if BLOCKED.search(value):
            return f"{value}: the gh config holds the token; use gh commands instead."
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = check(data.get("tool_input") or {})
    if reason:
        print(f"Blocked by .claude/hooks/guard_read.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
