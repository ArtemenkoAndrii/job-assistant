#!/usr/bin/env bash
# Builds the application. One command, non-zero exit on failure (CLAUDE.md → Commands).
# The container image is built by CI (apps/jobfinder/Dockerfile) and deploy (#16).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/apps/jobfinder"

echo "== uv sync (locked)"
uv sync --locked
echo "== uv build"
uv build --out-dir "${TMPDIR:-/tmp}/jobfinder-dist"
