.PHONY: help install dev run serve watch test check clean abandon merge deploy-preview deploy-prod version bump-patch bump-minor bump-major set-version homebrew-formula homebrew-push homebrew-tap-clone
.DEFAULT_GOAL := help

BRANCH_PROD := main
SRC_DIRS    := src/ tests/
VENV        := .venv
PIP         := $(VENV)/bin/pip
PYTEST      := $(VENV)/bin/pytest
PYTHON      := $(VENV)/bin/python3
OMON        := $(VENV)/bin/omon

# ── Helpers ───────────────────────────────────────────────────────────────────

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

_ensure-venv:
	@test -x $(PYTEST) || (echo "error: run 'make install' first" >&2; exit 1)

# ── Development ───────────────────────────────────────────────────────────────

install: ## Create .venv and install package with dev extras
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install -e ".[dev]"

dev: install ## Show common local test commands (Code Cannon DEV_CMD)
	@echo "Local omon from .venv — use these while developing:"
	@echo "  make run ARGS='list'          # decoded inventory"
	@echo "  make run ARGS='watch'         # live TUI"
	@echo "  make serve                    # web dashboard → http://127.0.0.1:11435"
	@echo "  make run ARGS='bench MODEL'   # benchmark"
	@echo ""
	@echo "Shell 'omon' may be pipx/Homebrew; make targets use .venv/bin/omon."

run: install ## Run omon subcommand (ARGS='watch' or ARGS='list --json')
	@if [ -z "$(ARGS)" ]; then echo "error: usage: make run ARGS='...'" >&2; exit 1; fi
	$(OMON) $(ARGS)

serve: install ## Start web dashboard
	@echo "Web dashboard: http://127.0.0.1:11435 (Ctrl+C to stop)"
	$(OMON) serve

watch: ## Run live monitoring TUI (alias for make run ARGS=watch)
	@$(MAKE) run ARGS=watch

test: install ## Run test suite (matches CI)
	$(PYTEST) -v

check: ## Full quality gate: tests
	@$(MAKE) test

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# ── Workflow (CodeCannon) ─────────────────────────────────────────────────────

abandon: ## Discard changes, delete feature branch, return to main
	@BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "$(BRANCH_PROD)" ]; then \
		echo "error: already on $(BRANCH_PROD), nothing to abandon" >&2; exit 1; \
	fi; \
	git checkout $(BRANCH_PROD) && \
	git pull --ff-only && \
	git branch -D "$$BRANCH" && \
	echo "Deleted branch $$BRANCH, now on $(BRANCH_PROD)"

merge: ## Merge current branch's PR into main
	gh pr merge --merge --delete-branch

deploy-preview: ## Deploy to preview (not configured)
	@echo "No preview deployment — omon is a local CLI. Run 'make dev' for local test commands."

deploy-prod: _ensure-venv ## Test, build, commit, tag, push, and publish (run after make bump-*)
	@$(MAKE) check
	$(PIP) install -q build
	$(PYTHON) -m build
	@V=$$($(MAKE) -s version); \
	LTAG=$$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-version:refname 2>/dev/null | head -n1); \
	if [ -n "$$LTAG" ]; then \
		LV=$${LTAG#v}; \
		if [ "$$V" = "$$LV" ] && git diff --quiet HEAD -- pyproject.toml src/omon/__init__.py; then \
			if gh release view "v$$V" >/dev/null 2>&1; then \
				echo "error: v$$V is already released — run make bump-patch, bump-minor, or bump-major first" >&2; \
				exit 1; \
			fi; \
		fi; \
	fi; \
	git add pyproject.toml src/omon/__init__.py; \
	if ! git diff --cached --quiet; then \
		git commit -m "chore: release v$$V"; \
	fi; \
	if ! git rev-parse "v$$V" >/dev/null 2>&1; then \
		git tag -a "v$$V" -m "Release v$$V"; \
	fi; \
	echo "Publishing v$$V..."; \
	git push && git push --tags; \
	gh release create "v$$V" --generate-notes; \
	echo "Published v$$V (PyPI + Homebrew via CI)"

# ── Homebrew tap ──────────────────────────────────────────────────────────────
# Auto-bump on release: .github/workflows/homebrew.yml (needs HOMEBREW_TAP_TOKEN).
# Makefile targets are for local preview or manual fallback after the tag is on GitHub.

HOMEBREW_TAP_REPO ?= LightbridgeLab/homebrew-omon
HOMEBREW_TAP_DIR  ?= ../OllamaMon_Homebrew_Tap

homebrew-tap-clone: ## Clone or update local tap repo (HOMEBREW_TAP_DIR)
	@chmod +x scripts/homebrew-tap-clone.sh
	@HOMEBREW_TAP_REPO="$(HOMEBREW_TAP_REPO)" HOMEBREW_TAP_DIR="$(HOMEBREW_TAP_DIR)" \
		./scripts/homebrew-tap-clone.sh

homebrew-formula: ## Regenerate Formula/omon.rb (V=x.y.z or current; tag must exist on GitHub)
	@V="$${V:-$$($(MAKE) -s version)}"; \
	./scripts/update-homebrew-formula.sh "$$V"

homebrew-push: homebrew-formula ## Copy formula to tap clone and push (HOMEBREW_TAP_DIR)
	@test -d "$(HOMEBREW_TAP_DIR)/.git" || { \
		echo "error: run 'make homebrew-tap-clone' first (expected clone at '$(HOMEBREW_TAP_DIR)')" >&2; \
		exit 1; \
	}
	@V="$${V:-$$($(MAKE) -s version)}"; \
	git -C "$(HOMEBREW_TAP_DIR)" pull --rebase origin main; \
	cp homebrew-omon/Formula/omon.rb "$(HOMEBREW_TAP_DIR)/Formula/omon.rb"; \
	cp homebrew-omon/README.md "$(HOMEBREW_TAP_DIR)/README.md"; \
	cd "$(HOMEBREW_TAP_DIR)" && \
		git add Formula/omon.rb README.md && \
		git diff --cached --quiet && { echo "tap unchanged"; exit 0; } || \
		(git commit -m "omon $$V" && git push); \
	echo "Pushed homebrew tap for v$$V"

# ── Versioning ────────────────────────────────────────────────────────────────

version: ## Print current version
	@python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"

bump-patch: ## Bump patch version in pyproject.toml and __init__.py (0.5.0 → 0.5.1)
	@V=$$(python3 -c "import tomllib; v = tomllib.load(open('pyproject.toml','rb'))['project']['version'].split('.'); v[2] = str(int(v[2])+1); print('.'.join(v))"); \
	$(MAKE) set-version V=$$V; \
	echo "Bumped to v$$V — run: make deploy-prod"

bump-minor: ## Bump minor version in pyproject.toml and __init__.py (0.5.0 → 0.6.0)
	@V=$$(python3 -c "import tomllib; v = tomllib.load(open('pyproject.toml','rb'))['project']['version'].split('.'); v[1] = str(int(v[1])+1); v[2] = '0'; print('.'.join(v))"); \
	$(MAKE) set-version V=$$V; \
	echo "Bumped to v$$V — run: make deploy-prod"

bump-major: ## Bump major version in pyproject.toml and __init__.py (0.5.0 → 1.0.0)
	@V=$$(python3 -c "import tomllib; v = tomllib.load(open('pyproject.toml','rb'))['project']['version'].split('.'); v[0] = str(int(v[0])+1); v[1] = '0'; v[2] = '0'; print('.'.join(v))"); \
	$(MAKE) set-version V=$$V; \
	echo "Bumped to v$$V — run: make deploy-prod"

set-version: ## Set version to V=x.y.z (pyproject.toml + src/omon/__init__.py)
	@if [ -z "$(V)" ]; then echo "error: usage: make set-version V=x.y.z" >&2; exit 1; fi
	@echo "$(V)" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$$' || { echo "error: invalid version '$(V)'" >&2; exit 1; }
	@python3 -c "import re, pathlib; v = '$(V)'; files = [(pathlib.Path('pyproject.toml'), r'version = \".*?\"', f'version = \"{v}\"'), (pathlib.Path('src/omon/__init__.py'), r'__version__ = \".*?\"', f'__version__ = \"{v}\"')]; [p.write_text(re.sub(pat, repl, p.read_text(), count=1)) for p, pat, repl in files]"
	@echo "Version set to $(V)"
