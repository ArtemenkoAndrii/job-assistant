#!/usr/bin/env python3
"""Fails on infrastructure patterns that ADR-0008 and ADR-0009 forbid.

- A workflow that uses `pull_request_target` (it runs with secrets on untrusted code).
- Terraform that grants anything to `allUsers` or `allAuthenticatedUsers` (the service is
  reachable only through IAP).
Comment lines are ignored, so a rule can be explained next to the code.
"""
import pathlib
import re
import sys

WORKFLOW_RULE = (re.compile(r"\bpull_request_target\b"), "pull_request_target is not allowed (ADR-0009)")
TERRAFORM_RULE = (re.compile(r"\ball(Authenticated)?Users\b"), "allUsers/allAuthenticatedUsers is not allowed (ADR-0008)")


def _scan(paths, rule, root):
    pattern, message = rule
    errors = []
    for path in sorted(paths):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            match = pattern.search(line)
            if match:
                errors.append(f"{path.relative_to(root)}:{n}: {match.group(0)}: {message}")
    return errors


def find_errors(root):
    root = pathlib.Path(root)
    workflows = [p for ext in ("yml", "yaml") for p in (root / ".github").rglob(f"*.{ext}")]
    terraform = list((root / "infra").rglob("*.tf"))
    return _scan(workflows, WORKFLOW_RULE, root) + _scan(terraform, TERRAFORM_RULE, root)


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    errors = find_errors(root)
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
