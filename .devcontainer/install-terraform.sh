#!/bin/bash
# Installs Terraform into the given directory. Used by the Dockerfile and CI, so both run the
# same version: the one in infra/.terraform-version (ADR-0009). The zip is verified against the
# SHA256 pinned in the repo, infra/.terraform-sha256 (same format as `sha256sum`), not against a
# checksum file downloaded from the release host. The hashes come from the official release page.
# Usage: install-terraform.sh <bin-dir>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA="$HERE/../infra"
VERSION="${TERRAFORM_VERSION:-$(tr -d '[:space:]' < "$INFRA/.terraform-version")}"
SUMS="${TERRAFORM_SHA256_FILE:-$INFRA/.terraform-sha256}"
BIN_DIR="${1:?usage: install-terraform.sh <bin-dir>}"

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

ZIP="terraform_${VERSION}_linux_${ARCH}.zip"
EXPECTED="$(awk -v z="$ZIP" '$2 == z { print $1 }' "$SUMS")"
if ! [[ "$EXPECTED" =~ ^[0-9a-f]{64}$ ]]; then
  echo "no pinned SHA256 for $ZIP in $SUMS (found: '${EXPECTED:-nothing}'); fill it from the official release page" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -o "$TMP/$ZIP" "https://releases.hashicorp.com/terraform/${VERSION}/${ZIP}"
echo "${EXPECTED}  ${ZIP}" | (cd "$TMP" && sha256sum -c -)
unzip -q -o "$TMP/$ZIP" terraform -d "$TMP"
install -m 0755 "$TMP/terraform" "$BIN_DIR/terraform"
"$BIN_DIR/terraform" version
