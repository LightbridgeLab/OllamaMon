#!/usr/bin/env bash
# Clone or update the local homebrew-omon tap working copy.
# Usage: ./scripts/homebrew-tap-clone.sh

set -euo pipefail

HOMEBREW_TAP_REPO="${HOMEBREW_TAP_REPO:-LightbridgeLab/homebrew-omon}"
HOMEBREW_TAP_DIR="${HOMEBREW_TAP_DIR:-../OllamaMon_Homebrew_Tap}"
URL="https://github.com/${HOMEBREW_TAP_REPO}.git"

if [[ -d "${HOMEBREW_TAP_DIR}/.git" ]]; then
  echo "Updating ${HOMEBREW_TAP_DIR}..."
  git -C "${HOMEBREW_TAP_DIR}" pull --ff-only
else
  echo "Cloning ${URL} -> ${HOMEBREW_TAP_DIR}..."
  git clone "${URL}" "${HOMEBREW_TAP_DIR}"
fi

echo "Tap clone ready at ${HOMEBREW_TAP_DIR}"
