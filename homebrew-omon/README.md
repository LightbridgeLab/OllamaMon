# homebrew-omon

Homebrew tap for [omon](https://github.com/LightbridgeLab/OllamaMon).

## Install

```bash
brew tap LightbridgeLab/omon
brew install omon
```

## Upgrade

```bash
brew update
brew upgrade omon
```

## Publish this tap (maintainers)

This directory is the source for the **`LightbridgeLab/homebrew-omon`** GitHub repository (required name for `brew tap LightbridgeLab/omon`).

### First-time setup

```bash
cd homebrew-omon
git init
git add Formula/omon.rb README.md
git commit -m "feat: initial omon formula"
gh repo create LightbridgeLab/homebrew-omon --public --source=. --push
```

### Update formula for a new release

From the **OllamaMon** repo root after tagging `vX.Y.Z`:

```bash
./scripts/update-homebrew-formula.sh X.Y.Z
```

Then commit and push in the `homebrew-omon` clone, or let the GitHub Action update the tap automatically (see [PUBLISHING.md](../PUBLISHING.md)).
