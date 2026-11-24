#!/usr/bin/env python3
"""Fails if a tracked Markdown file links to a repo file or folder that does not exist.

Only relative links are checked; web links are not fetched (CI must not depend on
outside sites). Code blocks and template placeholders (<...>) are skipped.
"""
import pathlib
import re
import subprocess
import sys

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def main():
    root = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    files = subprocess.check_output(["git", "ls-files", "*.md"], cwd=root, text=True).split()
    errors = []
    for rel in files:
        path = root / rel
        in_code = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            line = re.sub(r"`[^`]*`", "", line)
            for target in LINK.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#") or "<" in target:
                    continue
                target = target.split("#", 1)[0]
                if target.startswith("/"):
                    resolved = root / target.lstrip("/")
                else:
                    resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    errors.append(f"{rel}:{n}: broken link -> {target}")
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
