#!/usr/bin/env python3
"""PreToolUse hook for Bash: blocks commands that bypass review or touch secrets.

Claude Code passes the tool call as JSON on stdin. Exit code 2 blocks the call and
shows stderr to the agent. Rules: ADR-0003 (branching) and CLAUDE.md (rules).
"""
import json
import re
import subprocess
import sys

RULES = [
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*(\s--force\b|\s--force-with-lease\b|\s-[a-zA-Z]*f\b|\s\+\S)",
     "force-push is not allowed (ADR-0003). Merge main into the branch instead."),
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*(\s|:)(refs/heads/)?(main|master)(?=$|[\s;|&])",
     "pushing to main is not allowed (ADR-0003). Push the issue branch and open a PR."),
    (r"\bgit\b[^|;&]*\s--no-verify\b",
     "--no-verify skips the secret scan; fix the finding instead."),
    (r"\bgit\b[^|;&]*\bcore\.hooksPath\b",
     "changing core.hooksPath disables the pre-commit secret scan."),
    (r"\bgh\s+repo\s+(delete|edit|rename|archive)\b",
     "repository settings are changed by the owner, not by agents."),
    (r"\bgh\s+api\b[^|;&]*\brulesets?\b",
     "rulesets are changed by the owner, not by agents (ADR-0003)."),
    (r"\bgh\s+api\b[^|;&]*(-X|--method)\s*DELETE\b",
     "DELETE through the GitHub API is not allowed for agents."),
    (r"\bgh\s+auth\s+token\b",
     "printing the GitHub token is not allowed."),
    (r"\.config/gh\b",
     "the gh config holds the token; use gh commands, do not read its files."),
    (r"(^|[\s'\"=/<>])\.env(\.(?!example\b)[\w.-]+)?($|[\s'\";|&)])",
     ".env files hold secrets; agents do not read or write them."),
    (r"(^|[\s'\"=/])secrets/",
     "secrets/ folders are off limits for agents."),
]


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd or None,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check(command, cwd=None, branch=None):
    """Return a reason string if the command must be blocked, else None."""
    for pattern, reason in RULES:
        if re.search(pattern, command):
            return reason
    # A bare `git push` (no refspec) while on main pushes main.
    if re.search(r"\bgit\b[^|;&]*\bpush\b", command):
        if branch is None:
            branch = current_branch(cwd)
        if branch in ("main", "master"):
            return "you are on main; pushing from it is not allowed (ADR-0003). Create an issue branch."
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    reason = check(command, data.get("cwd"))
    if reason:
        print(f"Blocked by .claude/hooks/guard_bash.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
