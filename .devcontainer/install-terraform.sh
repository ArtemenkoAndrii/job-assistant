#!/bin/bash
# Installs Terraform into the given directory. Used by the Dockerfile and CI, so both run the
# same version: the one in infra/.terraform-version (ADR-0009). Verifies the zip against the
# release's SHA256SUMS file.
# Usage: install-terraform.sh <bin-dir>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${TERRAFORM_VERSION:-$(tr -d '[:space:]' < "$HERE/../infra/.terraform-version")}"
BIN_DIR="${1:?usage: install-terraform.sh <bin-dir>}"

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

ZIP="terraform_${VERSION}_linux_${ARCH}.zip"
BASE="https://releases.hashicorp.com/terraform/${VERSION}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -o "$TMP/$ZIP" "$BASE/$ZIP"
curl -fsSL -o "$TMP/SHA256SUMS" "$BASE/terraform_${VERSION}_SHA256SUMS"
(cd "$TMP" && grep " ${ZIP}\$" SHA256SUMS | sha256sum -c -)
unzip -q -o "$TMP/$ZIP" terraform -d "$TMP"
install -m 0755 "$TMP/terraform" "$BIN_DIR/terraform"
"$BIN_DIR/terraform" version
