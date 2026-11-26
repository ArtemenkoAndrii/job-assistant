#!/usr/bin/env python3
"""Fails on infrastructure patterns that ADR-0008 and ADR-0009 forbid.

- A workflow that uses `pull_request_target` (it runs with secrets on untrusted code).
- Terraform that grants anything to `allUsers` or `allAuthenticatedUsers` (the service is
  reachable only through IAP).
- A Terraform pin that is inconsistent: the Dockerfile version differs from infra/.terraform-version,
  or infra/.terraform-sha256 lacks a well-formed hash for linux_amd64 or linux_arm64. A placeholder
  hash is a warning locally and an error when CI is set.
Comment lines are ignored, so a rule can be explained next to the code.
"""
import os
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


PLACEHOLDER = "REPLACE_WITH_SHA256_FROM_RELEASE_PAGE"
ARCHES = ("amd64", "arm64")


def _version_errors(root, ci):
    """Terraform pin: version file, Dockerfile ARG and the pinned zip hashes must agree."""
    pinned_file = root / "infra" / ".terraform-version"
    if not pinned_file.exists():
        return []
    pinned = pinned_file.read_text(encoding="utf-8").strip()
    errors = []

    dockerfile = root / ".devcontainer" / "Dockerfile"
    if dockerfile.exists():
        match = re.search(r"^ARG TERRAFORM_VERSION=(\S+)", dockerfile.read_text(encoding="utf-8"), re.M)
        if match and match.group(1) != pinned:
            errors.append(
                f".devcontainer/Dockerfile: TERRAFORM_VERSION {match.group(1)} differs from infra/.terraform-version {pinned}"
            )

    sums_file = root / "infra" / ".terraform-sha256"
    if not sums_file.exists():
        return errors + ["infra/.terraform-sha256: missing (pinned zip hashes, see .devcontainer/install-terraform.sh)"]
    hashes = {}
    for line in sums_file.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            hashes[parts[1]] = parts[0]
    for arch in ARCHES:
        zip_name = f"terraform_{pinned}_linux_{arch}.zip"
        value = hashes.get(zip_name)
        if value is None:
            errors.append(f"infra/.terraform-sha256: no hash for {zip_name}")
        elif value == PLACEHOLDER:
            message = f"infra/.terraform-sha256: placeholder for {arch}, fill it from the official release page"
            if ci:
                errors.append(message)
            else:
                print(f"warning: {message}")
        elif not re.fullmatch(r"[0-9a-f]{64}", value):
            errors.append(f"infra/.terraform-sha256: malformed SHA256 for {arch}")
    if dockerfile.exists():
        text = dockerfile.read_text(encoding="utf-8")
        for arch in ARCHES:
            match = re.search(rf"^ARG TERRAFORM_SHA256_{arch.upper()}=(\S+)", text, re.M)
            expected = hashes.get(f"terraform_{pinned}_linux_{arch}.zip")
            if match and expected and match.group(1) != expected:
                errors.append(f".devcontainer/Dockerfile: TERRAFORM_SHA256_{arch.upper()} differs from infra/.terraform-sha256")
    return errors


def find_errors(root, ci=False):
    root = pathlib.Path(root)
    workflows = [p for ext in ("yml", "yaml") for p in (root / ".github").rglob(f"*.{ext}")]
    terraform = list((root / "infra").rglob("*.tf"))
    return _scan(workflows, WORKFLOW_RULE, root) + _scan(terraform, TERRAFORM_RULE, root) + _version_errors(root, ci)


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    errors = find_errors(root, ci=bool(os.environ.get("CI")))
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
