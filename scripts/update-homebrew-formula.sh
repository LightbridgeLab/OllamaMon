#!/usr/bin/env bash
# Regenerate homebrew-omon/Formula/omon.rb for a GitHub release tag.
# Usage: ./scripts/update-homebrew-formula.sh 0.5.0

set -euo pipefail

VERSION="${1:?Usage: $0 VERSION (e.g. 0.5.0)}"
REPO="${GITHUB_REPOSITORY:-LightbridgeLab/OllamaMon}"
URL="https://github.com/${REPO}/archive/refs/tags/v${VERSION}.tar.gz"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

curl -fsSL "$URL" -o "$TMP"
SHA256="$(shasum -a 256 "$TMP" | awk '{print $1}')"

OUT="$(cd "$(dirname "$0")/.." && pwd)/homebrew-omon/Formula/omon.rb"

cat > "$OUT" <<EOF
class Omon < Formula
  include Language::Python::Virtualenv

  desc "Local-first monitoring and management tool for Ollama"
  homepage "https://github.com/${REPO}"
  url "${URL}"
  sha256 "${SHA256}"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/omon --version")
  end
end
EOF

echo "Updated ${OUT} for v${VERSION} (sha256: ${SHA256})"
