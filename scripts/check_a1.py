#!/usr/bin/env python3
"""Fails if anything outside the runtime and spike kits references the Browser MCP endpoint (A-1).

CLAUDE.md: never touch real job boards from tests, CI or the dev container; A-1 is
reachable only from runtime and spike kits. Its credentials are the Cloudflare Access
service-token headers, so any use of them outside the allowed paths is a finding.
The runtime's only A-1 client is `browser/mcp_session.py` (#71); it and its test may use them.
"""
import re
import subprocess
import sys

PATTERNS = [
    r"CF[-_]Access[-_]Client[-_](Id|Secret)",
    r"cfargotunnel\.com",
    r"trycloudflare\.com",
]
# Documentation may describe A-1; these files define or test the check itself.
ALLOWED = re.compile(
    r"^(spikes/|docs/|.*\.md$|scripts/check_a1\.py$|\.claude/hooks/|tests/hooks/"
    r"|apps/jobfinder/src/jobfinder/browser/mcp_session\.py$"
    r"|apps/jobfinder/tests/unit/test_mcp_session\.py$)"
)


def main():
    files = subprocess.check_output(["git", "ls-files"], text=True).split("\n")
    errors = []
    for rel in filter(None, files):
        if ALLOWED.match(rel):
            continue
        try:
            text = open(rel, encoding="utf-8").read()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if any(re.search(p, line, re.I) for p in PATTERNS):
                errors.append(f"{rel}:{n}: A-1 reference outside runtime/spikes")
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
