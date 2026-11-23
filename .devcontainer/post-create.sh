#!/bin/bash
# Merges the container-level Claude Code settings into the user settings in $CLAUDE_CONFIG_DIR.
# Keys from claude-settings.json win, so the sandbox cannot be switched off by an old settings file.
# These settings apply only inside the dev container, not to Claude Code on the host.
set -euo pipefail

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MANAGED="/usr/local/share/devcontainer/claude-settings.json"
TARGET="$CONFIG_DIR/settings.json"

mkdir -p "$CONFIG_DIR"
if [ -f "$TARGET" ]; then
  jq -s '.[0] * .[1]' "$TARGET" "$MANAGED" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
else
  cp "$MANAGED" "$TARGET"
fi
echo "Claude Code settings: sandbox enabled, failIfUnavailable=true ($TARGET)"
