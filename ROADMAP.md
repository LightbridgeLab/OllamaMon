# omon — Roadmap

Features planned for future development, roughly ordered by priority. These are tracked here until we move to GitHub Issues.

---

## External Data Source Integration

**Phase:** Post-v0.4
**Depends on:** Phase 4 (Intelligence) foundation

Integrate optional, cached lookups from external APIs to enrich model information and power recommendations. All calls are opt-in — omon works fully offline by default.

### Data Sources

| Source | Data Available | Access |
|---|---|---|
| **OpenRouter** `/api/v1/models` | 349 models: descriptions, HuggingFace ID mapping, context lengths, pricing | No auth, JSON, `urllib` compatible |
| **HuggingFace** `/api/models/{id}` | Downloads, likes, param counts, architecture, tags, file listings | No auth (rate-limited), JSON |
| **Open LLM Leaderboard** via HF Datasets Server | 4,576 models: IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO scores | No auth, JSON, paginated |
| **Chatbot Arena** via HF Datasets Server | 8,423 models: Elo ratings, human preference rankings across text/vision/code | No auth, JSON, paginated |

### Implementation Plan

1. Add `external.py` module with individual client functions per source
2. Cache responses in SQLite with configurable TTL (default 24h)
3. Build Ollama → HuggingFace name mapping using:
   - OpenRouter's `hugging_face_id` field (~174 models have direct mapping)
   - `data/model_map.json` for curated known mappings
   - Fuzzy matching as fallback (with confidence indicator)
4. Surface enriched data in `omon show` and `omon suggest` commands
5. Add `omon enrich` command to manually trigger a full cache refresh

### What We Don't Build

- A model search engine or leaderboard replica
- Our own benchmark scoring system for model quality
- A comprehensive model database — lean on external sources

---

## Multi-Instance Monitoring

**Phase:** v1.0+

Support monitoring Ollama instances on remote machines.

```
omon --host 192.168.1.50:11434 list
omon --host mynas:11434 watch
```

### Design Notes

- All commands already go through `api.py` — adding a `--host` flag is architecturally trivial
- Config file could store named hosts: `omon --host workstation list`
- `omon watch` could show multiple instances side-by-side in the TUI
- Consider mDNS/Bonjour discovery for local network Ollama instances
- Security: Ollama's API has no auth by default — document the implications of remote access

---

## Import / Export Model Setups

**Phase:** v1.0+

Share and reproduce model inventories across machines.

```
omon export > my-setup.json          # Export current model list
omon import my-setup.json            # Pull all models from a setup file
omon export --with-benchmarks        # Include local benchmark results
```

### Use Cases

- "Here's what I run for coding on an M4 Max 64GB" — shareable community setups
- Reproduce a known-good configuration on a new machine
- Team standardization — "everyone should have these models"

### Format

JSON file containing:
- Model names and tags
- Hardware profile of the exporting machine
- Optional: benchmark results, notes, task assignments
- Does NOT contain model weights — just the names needed for `ollama pull`

---

## Notification System

**Phase:** v1.0+

Optional alerts for model and system events.

### Potential Triggers

- Model finished loading / unloading
- Generation speed dropped below threshold
- Memory pressure critical (swap in use)
- New version of installed model available
- Benchmark completed

### Delivery Mechanisms (in priority order)

1. Terminal bell (simplest, works everywhere)
2. macOS notifications via `osascript` (no dependency)
3. Webhook (POST to a URL — enables Slack, Discord, etc.)

---

## Distribution & Packaging

**Phase:** Pre-v1.0
**Depends on:** GitHub repo, CI/CD pipeline

Make omon installable via common package managers beyond pip/pipx.

### Channels (in priority order)

| Channel | Type | Review Required | Notes |
|---|---|---|---|
| **PyPI** | Foundation | No | Done — `pipx install omon` via Trusted Publishing (OIDC). |
| **Homebrew tap** | Self-hosted | No | Done — `homebrew-omon/` in repo; publish to `LightbridgeLab/homebrew-omon`. Users: `brew tap LightbridgeLab/omon && brew install omon`. |
| **AUR** | Community | No | `PKGBUILD` + `.SRCINFO` pushed to aur.archlinux.org. Live immediately. |
| **Nix flake** | In-repo | No | `flake.nix` in project root. Users: `nix profile install github:user/omon`. |
| **conda-forge** | PR-based | Yes (1-2 weeks) | Submit recipe to `conda-forge/staged-recipes`. After merge, bot auto-bumps on new PyPI releases. |
| **nixpkgs** | PR-based | Yes (1-4 weeks) | PR to `NixOS/nixpkgs` adding `pkgs/by-name/om/omon/package.nix`. |
| **homebrew-core** | PR-based | Yes (weeks-months) | Requires "notability" — build user base first via tap + PyPI. |

### Prerequisites

1. Public GitHub repo with tagged releases and source tarballs
2. CI workflow (GitHub Actions) that on tag push: runs tests, builds sdist+wheel, publishes to PyPI, creates GitHub Release
3. Complete `pyproject.toml` metadata (authors, classifiers, project.urls)

### What We Skip

- **Debian/Ubuntu PPA** — rigid format, months-long review, poor effort-to-reach for a solo project
- **Snap/Flatpak** — designed for GUI apps, awkward for CLI tools
- **Docker** — adds network complexity for a tool that talks to local Ollama; revisit if multi-instance lands

### Per-Release Workflow (once set up)

1. Bump version in `pyproject.toml` + `src/omon/__init__.py`
2. Commit, tag, push — CI publishes to PyPI and creates GitHub Release
3. Update Homebrew tap formula (URL + sha256) — automatable via GitHub Action
4. Update AUR PKGBUILD (pkgver + sha256) — automatable via GitHub Action
5. conda-forge bot auto-opens a version bump PR — just merge it

