# omon — Ollama Monitor

> **Status:** Original design document. Phases 1–4 are implemented (v0.5.0). Phase 5 (distribution polish) and `external.py` are deferred — see [ROADMAP.md](ROADMAP.md).

A simple, local-first, privacy-focused monitoring and management tool for Ollama.

**Command name:** `omon` (not `ollama-mon` — shorter, no autocomplete collision with `ollama` commands)
**Package name:** `omon` on PyPI and Homebrew (for discoverability, `ollama-mon` redirects)
**Language:** Python 3.10+
**Dependencies:** Zero. Python stdlib only.

---

## The Problem

Ollama's built-in CLI (`ollama list`, `ollama show`, `ollama ps`) provides raw data but no interpretation. Users are left guessing:

1. **What do I have?** — Total disk usage across all models. What do cryptic tag names like `35b-a3b-coding-nvfp4` actually mean?
2. **Is this any good?** — Am I getting decent performance from this model on my hardware? What's my tokens/s? Is this model too big for my machine?
3. **What should I use instead?** — Is there a newer version? A better model for my task? Something faster that fits my hardware?
4. **Am I using my hardware well?** — I have an M4 Max with 64GB. What can I actually run? What's wasted?

No existing tool answers these questions simply. GPU monitors (nvtop, macmon) don't know about models or tokens. Chat UIs (Open WebUI) aren't monitoring tools. Grafana stacks are massive overkill for local use.

---

## What the Ollama API Already Provides

All data comes from `localhost:11434`. No scraping, no hacks.

| Endpoint | Data |
|---|---|
| `GET /api/tags` | Model list: name, size on disk, digest, family, param size, quantization |
| `POST /api/show` | Deep details: architecture, context length (e.g. 262K), capabilities (vision/thinking/tools), parameters, license, modelfile |
| `GET /api/ps` | Running models: memory footprint, VRAM usage, context length, expiry time |
| `POST /api/generate` | Inference with metrics: `load_duration`, `prompt_eval_count/duration`, `eval_count/duration` — enough to compute tok/s |
| `GET /api/version` | Server version |

This is rich data that `ollama list` barely surfaces.

---

## Development Phases

### Phase 1: Inventory & Understanding — "What do I have?" (v0.1)

The immediately useful foundation. Surfaces data already in the API but hidden.

**Commands:**

```
omon                              # Status overview (server health, loaded models, disk)
omon list                         # Enhanced model list with decoded names
omon list --cap vision            # Filter by capability
omon show <model>                 # Rich model info card
omon disk                         # Disk usage breakdown
omon pressure                     # Memory pressure status (macOS)
```

All commands support `--json` for structured output (piping to `jq`, scripts, etc.).

**`omon list` target output:**
```
Models (2)                                              Total: 24.8 GB

  qwen3.5:35b-a3b-coding-nvfp4                              21.0 GB
  │ Qwen 3.5 MoE · 35.1B params (3B active) · Coding fine-tune
  │ NVIDIA FP4 quant · 262K context · vision, thinking, tools
  │ Apache-2.0
  │ 2 weeks ago

  llama2:7b                                                   3.8 GB
  │ Llama 2 · 7B params · Q4_0 quant · 4K context
  │ Llama 2 Community License
  │ 2 weeks ago · successor available: llama3.3
```

**Model name decoder:** A pattern dictionary (not AI) that maps known fragments:
- `35b` → "35.1B params" (cross-referenced with API's `parameter_size`)
- `a3b` → "(3B active)" — MoE active parameter notation
- `coding` → "Coding fine-tune"
- `nvfp4` → "NVIDIA FP4 quant"
- Unknown fragments → displayed as-is, not guessed

**`omon show`** — full model card including:
- Architecture, parameters, template, capabilities
- License summary (one-line: "Apache-2.0" or "Llama 3 Community — non-commercial restrictions")
- Successor model hint (from `data/model_map.json`)
- Prompt template display

**`omon disk`** — breakdown by model, total usage, available disk space, layer sharing visibility (actual unique disk usage vs. nominal size when Ollama deduplicates base layers).

**`omon` (no args)** — status overview:
- Ollama server health: running/stopped, version, config (`OLLAMA_HOST`, `OLLAMA_MODELS`)
- Compatibility note if model requires newer Ollama version
- Loaded models with memory usage
- Total disk usage summary

**`omon pressure`** — macOS memory pressure:
- Current pressure level (normal/warn/critical) via `memory_pressure` / `vm_stat`
- Swap usage
- How much headroom exists for loading models
- Warning if current loaded models are causing pressure

**Deliverables:** Working CLI installable via `pip install -e .`, project scaffolding, `--json` on all commands, tests.

---

### Phase 2: Performance Monitoring — "How's it running?" (v0.2)

```
omon watch                        # Live TUI (curses)
omon bench <model>                # Quick benchmark
omon bench --compare m1 m2        # Side-by-side comparison
```

**`omon watch` — curses TUI:**
```
omon                                         M4 Max · 64 GB · 16 cores

  Active Models
  ─────────────────────────────────────────────────────────────────────
  llama2:7b          4.8 GB / 64 GB RAM    ████░░░░░░  7.5%
                     37.6 tok/s gen · 96.4 tok/s prompt
                     ctx: 4096 · loaded 2m ago · expires 3m

  Idle · Watching for activity...
```

**`omon bench` measures:**
- Cold load time (model not in memory → first token)
- Warm load time (model already cached)
- Prompt processing speed (tok/s)
- Generation speed (tok/s)
- Time to first token (TTFT)
- Memory footprint (from `/api/ps`)

Uses standardized test prompts of varying lengths (short, medium, long) to measure scaling behavior.

**`omon bench --compare`:** Runs the same benchmark suite against two models, shows results side-by-side.

**Also includes:**
- Combined memory impact when multiple models are loaded
- Concurrent model tracking ("3 models loaded, using 45GB of 64GB")
- Memory pressure integration in TUI (from Phase 1's `omon pressure`)
- Model staleness tracking — record last-used timestamps in SQLite, surface in `omon list` and `omon cleanup`

**Data storage:** SQLite database (`~/.local/share/omon/metrics.db`) for benchmark results, usage timestamps, and historical metrics. Enables trend tracking and cleanup suggestions in later phases.

---

### Phase 3: Web Dashboard — "Show me everything" (v0.3)

```
omon serve                        # Start web server on :11435
omon serve --port 9000            # Custom port
```

Built with `http.server` + vanilla HTML/CSS/JS. No React, no build step, no node_modules.

**Dashboard panels:**
- Model inventory with search/filter
- Live performance metrics (polling JSON API)
- Disk usage visualization
- Hardware utilization
- Benchmark history (from SQLite)

**Frontend approach:**
- Single HTML file with embedded CSS
- Vanilla JS, fetch() for data
- SVG-based charts (no Chart.js dependency)
- CSS custom properties for dark/light theme
- Responsive layout with CSS Grid

---

### Phase 4: Intelligence — "What should I use?" (v0.4)

```
omon hw                           # Hardware profile
omon suggest --task coding        # Model recommendations
omon updates                      # Check for newer versions
omon cleanup                      # Suggest models to remove
```

**Hardware profiling:**
- Detect chip, memory, cores (macOS: `sysctl`, Linux: `/proc`)
- Calculate comfortable model size ceiling (~75% of available memory)
- Warn about swap/memory pressure risk for large models

**Model recommendations** (see "External Data Strategy" below):
- Map installed models to benchmark scores (when available)
- "Similar but faster/smaller" suggestions based on hardware profile
- Task-oriented suggestions: "for coding on your hardware, consider X, Y, Z"

**Cleanup suggestions:**
- Models not used recently (track last-used in SQLite)
- Models with newer versions available
- Duplicate base layers / redundant quantizations

**Update checking:**
- Compare installed model digests against Ollama registry
- Show what's available vs what's installed

---

### Phase 5: Polish & Ship (v1.0)

- `pip install omon` / `pipx install omon`
- Homebrew formula
- Shell completions (bash/zsh/fish)
- Man page
- Configuration file (`~/.config/omon/config.toml` — parsed with stdlib `tomllib`)
- Historical trend charts in web dashboard
- CI/CD pipeline, release automation

See [ROADMAP.md](ROADMAP.md) for post-v1.0 features (multi-instance, import/export, notifications, external data integration).

---

## External Data Strategy

Four external APIs provide model metadata, benchmarks, and recommendations. All are free, require no authentication, and work with `urllib`. All external calls are **opt-in** — omon works fully offline by default.

### Sources

| Source | Endpoint | Data | Use Case |
|---|---|---|---|
| **OpenRouter** | `GET openrouter.ai/api/v1/models` | 349 models: descriptions, HuggingFace ID mapping, context lengths | Model descriptions, cross-referencing |
| **HuggingFace** | `GET huggingface.co/api/models/{id}` | Downloads, likes, param counts, architecture, tags | Popularity, metadata enrichment |
| **Open LLM Leaderboard** | HF Datasets Server API | 4,576 models: IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO scores | Benchmark comparison |
| **Chatbot Arena** | HF Datasets Server API | 8,423 models: Elo ratings, human preference rankings | Quality ranking |

### Integration Approach

1. **Local-first:** omon works entirely offline. External lookups happen only when the user runs `omon suggest` or `omon updates`, or explicitly enables enrichment.
2. **Cache aggressively:** External data is cached in SQLite with a configurable TTL (default: 24h). No repeated calls.
3. **Degrade gracefully:** If a lookup fails (no internet, rate limited, API changed), show what we have locally and note what's missing. Never error out.
4. **Name mapping:** The hardest problem. Ollama names (`llama3.2`) don't match HuggingFace names (`meta-llama/Llama-3.2-3B-Instruct`). Strategy:
   - Use OpenRouter's `hugging_face_id` field (covers ~174 models)
   - Use Ollama registry config blobs for `model_family` + `model_type`
   - Maintain a `data/model_map.json` for known mappings (community-maintained)
   - Fuzzy matching as a fallback, with confidence indicator

### What We Don't Build

We do NOT try to:
- Replicate leaderboard UIs (just link to them)
- Run our own benchmarks for quality/accuracy (that's what the leaderboards are for)
- Build a model search engine (just surface relevant info for installed models)
- Maintain a comprehensive model database (lean on external sources)

---

## Architecture

```
omon/
├── src/
│   └── omon/
│       ├── __init__.py          # Version string
│       ├── __main__.py          # python -m omon
│       ├── cli.py               # argparse, command dispatch
│       ├── api.py               # Ollama HTTP client (urllib only)
│       ├── models.py            # Dataclasses for model info
│       ├── decoder.py           # Model name/tag decoder
│       ├── hardware.py          # System detection (sysctl, /proc)
│       ├── pressure.py          # Memory pressure monitoring (macOS vm_stat, Linux /proc/meminfo)
│       ├── formatter.py         # Terminal output formatting (ANSI)
│       ├── bench.py             # Benchmarking logic
│       ├── store.py             # SQLite metrics storage
│       ├── external.py          # External API clients (planned — see ROADMAP.md)
│       ├── tui/
│       │   ├── __init__.py
│       │   └── watch.py         # curses live view
│       └── web/
│           ├── __init__.py
│           ├── server.py        # http.server handler
│           └── static/
│               ├── index.html
│               ├── style.css
│               └── app.js
├── data/
│   ├── tag_dictionary.json      # Known model name fragments
│   └── model_map.json           # Ollama → HuggingFace name mapping
├── tests/
│   ├── test_api.py
│   ├── test_decoder.py
│   ├── test_bench.py
│   └── ...
├── pyproject.toml
└── LICENSE                      # MIT
```

### Design Rules

1. **Zero external dependencies.** Enforced in `pyproject.toml`. No exceptions.
2. **`api.py` is the sole Ollama interface.** Everything else works with dataclasses.
3. **Progressive enhancement.** CLI works alone. TUI adds on. Web adds on. Each layer is optional.
4. **Offline by default.** External API calls are explicit, opt-in, and cached.
5. **Fail informatively.** If Ollama isn't running, say so clearly. If a model name can't be decoded, show what we know and flag the unknown parts.

---

## Feature Placement Summary

All agreed-upon features have been placed into specific phases:

| Feature | Phase |
|---|---|
| `--json` output on all commands | 1 |
| License awareness | 1 |
| Capability filtering (`--cap`) | 1 |
| Server health / compatibility check | 1 |
| Memory pressure monitoring | 1 |
| Layer sharing visibility (disk) | 1 |
| Prompt template display | 1 |
| Model staleness tracking | 2 |
| Cleanup suggestions | 4 |
| External data integration | ROADMAP |
| Multi-instance support | ROADMAP |
| Import/export model setups | ROADMAP |
| Notification system | ROADMAP |

---

## Open Questions

- **Proxy mode (future):** Should omon optionally sit between clients and Ollama to passively measure all inference? More invasive but enables continuous performance monitoring without benchmarks. Deferred — polling `/api/ps` + explicit benchmarks cover the MVP.
- **Windows/Linux support:** macOS is the primary target (Apple Silicon + Ollama is the sweet spot). Linux support is straightforward (sysctl → /proc). Windows is lower priority but shouldn't be blocked by architecture choices.
