#!/usr/bin/env python3
"""PreToolUse hook for Read/Grep/Glob: keeps the agent's tools out of credential folders.

The gh token in ~/.config/gh must stay readable for `gh` inside the sandbox, so it
cannot be a Read deny rule (the sandbox applies those to every command). This hook
blocks the agent's own file tools instead. Exit code 2 blocks the call.
"""
import json
import os
import re
import sys

BLOCKED = re.compile(r"(^|[/\\])\.config[/\\]gh([/\\]|$)")
GH_DIR = os.path.realpath(os.path.expanduser("~/.config/gh"))


def resolve(value):
    return os.path.realpath(os.path.expanduser(value))


def check(tool_input):
    """Return a reason string if the call must be blocked, else None."""
    for key in ("file_path", "path", "pattern", "glob"):
        value = str(tool_input.get(key) or "")
        if value and BLOCKED.search(os.path.normpath(value)):
            return f"{value}: the gh config holds the token; use gh commands instead."
    for key in ("file_path", "path"):
        value = str(tool_input.get(key) or "")
        if not value:
            continue
        target = resolve(value)
        if target == GH_DIR or target.startswith(GH_DIR + os.sep):
            return f"{value}: the gh config holds the token; use gh commands instead."
        # A recursive search starting above ~/.config/gh would reach the token.
        if key == "path" and GH_DIR.startswith(target.rstrip(os.sep) + os.sep):
            return (f"{value}: searching here would include ~/.config/gh (the gh token); "
                    "search inside the repo instead.")
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
