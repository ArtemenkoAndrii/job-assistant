#!/usr/bin/env bash
# Runs all static checks. One command, non-zero exit on failure (CLAUDE.md → Commands).
# Every check runs even if an earlier one fails, so one run shows all findings.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1

failed=()
run() {
  local name="$1"; shift
  echo "== $name"
  if "$@"; then echo "ok"; else failed+=("$name"); fi
}

check_shell() { git ls-files -z '*.sh' '.githooks/*' | xargs -0 -r shellcheck; }
check_json() { git ls-files -z '*.json' | xargs -0 -r -n1 jq empty; }

run "shellcheck" check_shell
run "json" check_json
run "markdown links" python3 scripts/check_md_links.py
run "A-1 only from runtime and spikes" python3 scripts/check_a1.py

# Python application (ADR-0005)
APP=apps/jobfinder
if command -v uv >/dev/null 2>&1; then
  run "ruff check" uv run --project "$APP" --locked ruff check "$APP"
  run "ruff format" uv run --project "$APP" --locked ruff format --check "$APP"
  run "pyright" bash -c "cd $APP && uv run --locked pyright"
elif [ -n "${CI:-}" ]; then
  echo "== python"; echo "uv is not installed"; failed+=("python")
else
  echo "== python"; echo "skipped: uv not installed (it is in the dev container and in CI)"
fi

if command -v gitleaks >/dev/null 2>&1; then
  run "gitleaks" gitleaks git --redact --no-banner .
elif [ -n "${CI:-}" ]; then
  echo "== gitleaks"; echo "gitleaks is not installed"; failed+=("gitleaks")
else
  echo "== gitleaks"; echo "skipped: gitleaks not installed (it is in the dev container and in CI)"
fi

if [ ${#failed[@]} -gt 0 ]; then
  echo "FAILED: ${failed[*]}"
  exit 1
fi
echo "All checks passed."
