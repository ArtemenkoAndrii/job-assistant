#!/usr/bin/env bash
# Scans locked Python dependencies for known vulnerabilities (NFR-S7). Needs network: CI step.
# pip-audit has no severity filter, so any finding fails. A finding that does not apply is
# ignored by ID below, with a reason.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/apps/jobfinder"

IGNORE=()  # e.g. IGNORE=(--ignore-vuln GHSA-xxxx-xxxx-xxxx)  # reason

reqs="$(mktemp)"
trap 'rm -f "$reqs"' EXIT
uv export --locked --no-dev --no-emit-project --format requirements.txt > "$reqs"
uv run --locked pip-audit --strict --disable-pip --requirement "$reqs" "${IGNORE[@]}"
