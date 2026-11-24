#!/usr/bin/env python3
"""PreToolUse hook for Write/Edit/MultiEdit/NotebookEdit: blocks secrets and secret files.

The repo is public (CLAUDE.md), so a secret written to a tracked file is one commit away
from leaking. Exit code 2 blocks the call and shows stderr to the agent.
Gitleaks (pre-commit and CI) is the second line of defence.
"""
import json
import re
import sys

SECRET_PATTERNS = [
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("AWS access key", r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    ("GitHub fine-grained token", r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    ("Anthropic API key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("OpenAI API key", r"\bsk-(proj-)?[A-Za-z0-9_-]{32,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("Cloudflare Access secret",
     r"CF[-_]Access[-_]Client[-_]Secret['\"]?\s*[:=]\s*['\"]?[0-9a-fA-F]{32,}"),
]

BLOCKED_PATHS = [
    (r"(^|/)\.env(\.(?!example$)[^/]+)?$", ".env files hold secrets"),
    (r"(^|/)secrets/", "secrets/ folders are off limits"),
    (r"\.(pem|key|p12|pfx)$", "key files are never written by agents"),
]


def texts(tool_input):
    if "content" in tool_input:
        yield tool_input.get("content") or ""
    if "new_string" in tool_input:
        yield tool_input.get("new_string") or ""
    if "new_source" in tool_input:
        yield tool_input.get("new_source") or ""
    for edit in tool_input.get("edits") or []:
        yield edit.get("new_string") or ""


def check(tool_input):
    """Return a reason string if the write must be blocked, else None."""
    path = (tool_input.get("file_path") or tool_input.get("notebook_path") or "").replace("\\", "/")
    for pattern, reason in BLOCKED_PATHS:
        if re.search(pattern, path):
            return f"{path}: {reason}."
    for text in texts(tool_input):
        for name, pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                return (f"{path}: looks like a {name}. The repo is public; secrets live in a "
                        "secret manager. Use a placeholder or an environment variable name.")
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = check(data.get("tool_input") or {})
    if reason:
        print(f"Blocked by .claude/hooks/guard_write.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
