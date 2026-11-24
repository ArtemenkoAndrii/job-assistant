#!/usr/bin/env bash
# Runs all tests. One command, non-zero exit on failure (CLAUDE.md → Commands).
# Product tests are added here with the stack decision (#46).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "== hook tests"
python3 -m unittest discover -s tests/hooks -p 'test_*.py' -v
