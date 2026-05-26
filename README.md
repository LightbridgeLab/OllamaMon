# omon

[![PyPI version](https://img.shields.io/pypi/v/omon)](https://pypi.org/project/omon/)
[![Homebrew](https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/LightbridgeLab/OllamaMon/main/pyproject.toml&query=%24.project.version&label=homebrew&logo=homebrew&color=FBB040)](https://github.com/LightbridgeLab/homebrew-omon)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/LightbridgeLab/OllamaMon/blob/main/LICENSE)
[![stdlib only](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](https://github.com/LightbridgeLab/OllamaMon/blob/main/pyproject.toml)

**Ollama tells you names. omon tells you what they mean.**

[GitHub](https://github.com/LightbridgeLab/OllamaMon) · [PyPI](https://pypi.org/project/omon/) · [Homebrew tap](https://github.com/LightbridgeLab/homebrew-omon) · [Issues](https://github.com/LightbridgeLab/OllamaMon/issues)

[Ollama](https://ollama.com)'s CLI shows model tags and file sizes. `omon` decodes those tags, benchmarks performance on your hardware, tracks what's eating your RAM, and tells you what to run — or remove.

![omon demo](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/demo.gif)

## Why omon?

- **Decode cryptic model names** — `35b-a3b-coding-nvfp4` becomes "Qwen3.5 · 35B (3B active) · Code generation · NVIDIA FP4 · vision, thinking, tools"
- **Benchmark on your machine** — cold/warm load times, tok/s, memory footprint; compare models side-by-side
- **Know what to run** — hardware-aware suggestions, successor alerts, cleanup recommendations for stale models
- **Local-first, zero dependencies** — Python stdlib only. No venv conflicts, no supply chain risk, no cloud calls

## Screenshots

Click an image for full size.

**Status overview** (`omon`)

[![omon status overview — click for full size](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/screenshots/overview.png)](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/screenshots/overview.png)

**Live TUI** (`omon watch`)

[![omon live TUI — click for full size](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/screenshots/watch.png)](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/screenshots/watch.png)

**Web dashboard** (`omon serve`)

[![omon web dashboard — click for full size](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/screenshots/web.png)](https://github.com/LightbridgeLab/OllamaMon/raw/main/assets/screenshots/web.png)

## Install

Pick one — you only need a single install path.

**PyPI** (macOS, Linux; recommended):

```bash
pipx install omon
# or: pip install omon
```

**Homebrew** (macOS):

```bash
brew tap LightbridgeLab/omon
brew install omon
```

**From source:**

```bash
pipx install git+https://github.com/LightbridgeLab/OllamaMon.git
```

Requires Python 3.10+ and a running [Ollama](https://ollama.com) instance.

**Upgrade:** `pipx upgrade omon` or `brew upgrade omon`

## Quick start

```bash
omon                          # status overview: server, models, RAM, pressure
omon list                     # decoded model inventory
omon bench llama3.2:3b        # benchmark load time and tok/s
omon watch                    # live TUI (press q to quit)
```

More commands: `omon hw`, `omon suggest --task coding`, `omon cleanup`, `omon serve`.

## Developing from source

```bash
git clone https://github.com/LightbridgeLab/OllamaMon.git && cd OllamaMon
make install
make dev              # common local test commands
make check            # run tests
```

See [AGENTS.md](https://github.com/LightbridgeLab/OllamaMon/blob/main/AGENTS.md) for architecture rules and the pipx/Homebrew vs `.venv` note.

## Developing from source

```bash
git clone https://github.com/LightbridgeLab/OllamaMon.git && cd OllamaMon
make install
make dev              # common local test commands
make check            # run tests
```

See [AGENTS.md](https://github.com/LightbridgeLab/OllamaMon/blob/main/AGENTS.md) for architecture rules and the pipx/Homebrew vs `.venv` note.

## Documentation

- [Command reference](https://github.com/LightbridgeLab/OllamaMon/blob/main/REFERENCE.md) — full docs for every command, config, and completions
- [Design history](https://github.com/LightbridgeLab/OllamaMon/blob/main/PLANNING.md) — how and why omon was built
- [Roadmap](https://github.com/LightbridgeLab/OllamaMon/blob/main/ROADMAP.md) — what's planned next
- [Security](https://github.com/LightbridgeLab/OllamaMon/blob/main/SECURITY.md) — network exposure and data storage
- [Contributing](https://github.com/LightbridgeLab/OllamaMon/blob/main/AGENTS.md) — architecture rules and conventions

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally (or `--host` for remote)
- macOS or Linux (Apple Silicon is the primary target)

## License

MIT — see [LICENSE](https://github.com/LightbridgeLab/OllamaMon/blob/main/LICENSE).
