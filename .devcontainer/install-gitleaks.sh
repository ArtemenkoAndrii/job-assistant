#!/bin/bash
# Installs gitleaks (secret scanner) into the given directory. Used by the Dockerfile and CI,
# so both run the same version. Verifies the archive against the release checksums.
# Usage: install-gitleaks.sh <bin-dir>
set -euo pipefail

VERSION="${GITLEAKS_VERSION:-8.21.2}"
BIN_DIR="${1:?usage: install-gitleaks.sh <bin-dir>}"

case "$(uname -m)" in
  x86_64) ARCH=x64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

TARBALL="gitleaks_${VERSION}_linux_${ARCH}.tar.gz"
BASE="https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -o "$TMP/$TARBALL" "$BASE/$TARBALL"
curl -fsSL -o "$TMP/checksums.txt" "$BASE/gitleaks_${VERSION}_checksums.txt"
(cd "$TMP" && grep " ${TARBALL}\$" checksums.txt | sha256sum -c -)
tar -xzf "$TMP/$TARBALL" -C "$TMP" gitleaks
install -m 0755 "$TMP/gitleaks" "$BIN_DIR/gitleaks"
"$BIN_DIR/gitleaks" version
