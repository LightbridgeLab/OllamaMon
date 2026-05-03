# omon

A simple, local-first monitoring and management tool for [Ollama](https://ollama.com).

`ollama list` shows you names and sizes. `omon` tells you what those names mean, how your models are performing, what's eating your RAM, and what you should be running instead.

**Zero dependencies.** Python stdlib only. No venv conflicts, no supply chain risk.

## Install

```bash
# With pipx (recommended — installs globally, isolated)
pipx install -e .

# Or with pip in a venv
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

Requires Python 3.10+ and a running Ollama instance.

## Commands

### `omon` — Status overview

```
omon · Ollama Monitor

  Server    running · v0.20.3 · localhost:11434
  Models    2 installed · 24.0 GB total
  Loaded    1 model · 4.8 GB RAM (7.5% of 64.0 GB)
  Memory    normal · 0 B swap · 27.6 GB available
  System    Apple M4 Max · 64.0 GB · 16 cores
```

### `omon list` — Decoded model inventory

Translates cryptic model tags into plain English. Shows capabilities, license, context length, and flags models with known successors.

```
Models (2)                                              Total: 24.0 GB

  qwen3.5:35b-a3b-coding-nvfp4                              20.4 GB
  │ Qwen3.5 · 35B (3B active) · Code generation
  │ NVIDIA FP4 quant · 256K context · vision, thinking, tools
  │ Apache-2.0
  │ 2 weeks ago

  llama2:7b                                                   3.6 GB
  │ Llama2 · 7B
  │ Q4_0 quant · 4K context
  │ Llama 2 Community
  │ 2 weeks ago · successor available: llama3.3
```

Filter by capability:

```bash
omon list --cap vision     # only models with vision support
omon list --cap thinking   # only models with chain-of-thought
```

### `omon show <model>` — Model details

Full model card with architecture, parameters, quantization description, prompt template, and more. Supports partial name matching.

```bash
omon show qwen3.5          # matches qwen3.5:35b-a3b-coding-nvfp4
```

```
qwen3.5:35b-a3b-coding-nvfp4
Latest Qwen MoE models with vision and thinking support

  Family          Qwen3.5
  Publisher       Alibaba / Qwen Team
  Parameters      35B (3B active per token)  (35,106,839,040 params)
  Quantization    NVIDIA FP4  (NVIDIA 4-bit floating point)
  Context         262,144 tokens (256K)
  Format          safetensors
  Capabilities    completion, vision, thinking, tools
  License         Apache-2.0
  Fine-tune       Code generation
  Requires        Ollama >= 0.19.0
```

### `omon bench <model>` — Performance benchmarks

Measures cold/warm load time, prompt processing, generation speed, and memory footprint across short, medium, and long prompts.

```
Benchmark: llama2:7b

  Cold Load       4.0s
  Warm Load       54ms
  Memory          4.8 GB

  Short Prompt (31 in → 100 out)
    Prompt Speed   676 tok/s
    Gen Speed      97.2 tok/s
    TTFT           71ms

  Medium Prompt (97 in → 300 out)
    Prompt Speed   935 tok/s
    Gen Speed      96.1 tok/s
    TTFT           121ms

  Long Prompt (208 in → 500 out)
    Prompt Speed   909 tok/s
    Gen Speed      95.3 tok/s
    TTFT           246ms

  Rating          Excellent — avg 96.2 tok/s generation
```

Compare two models side-by-side:

```bash
omon bench llama2:7b --compare qwen3.5:35b-a3b-coding-nvfp4
```

### `omon watch` — Live monitoring TUI

Curses-based live view showing loaded models, memory usage bars, and system pressure. Polls every 2 seconds.

```bash
omon watch     # or: omon top
```

Press `q` to quit.

### `omon serve` — Web dashboard

Starts a local web server with a dark-themed dashboard. Vanilla HTML/CSS/JS, no build step.

```bash
omon serve                  # http://localhost:11435
omon serve --port 9000      # custom port
```

Dashboard includes model inventory with search/filter, live memory and running model status, disk usage visualization, and benchmark history.

### `omon hw` — Hardware profile

Shows what your machine can handle.

```
Hardware Profile

  Chip            Apple M4 Max
  CPU Cores       16
  Memory          64.0 GB
  OS              macOS 15.7.5

  Model Sizing Guide
    Comfortable     up to ~48 GB models (75% of RAM)
    Maximum         up to ~58 GB models (90% of RAM, may cause pressure)

    Estimated max parameters (comfortable fit):
      Q2       ~171B parameters
      Q4       ~93B parameters
      Q8       ~51B parameters
      FP16     ~25B parameters
```

### `omon suggest` — Model recommendations

Suggests models for a task based on your hardware and what's already installed.

```bash
omon suggest --task coding
omon suggest --task vision
omon suggest                # defaults to 'general'
```

Available tasks: `general`, `coding`, `math`, `vision`, `chat`, `embedding`, `thinking`, `tools`.

### `omon updates` — Check for successors

```
Model Updates

  llama2:7b
    Successor: llama3.3
    Latest Llama text model, 70B with performance rivaling larger models
    Install: ollama pull llama3.3
```

### `omon cleanup` — Suggest removals

Flags models that are unused, stale, or superseded.

```
Cleanup Suggestions  · potential savings: 3.6 GB

  llama2:7b  3.6 GB
    · Never used (no recorded activity)
    · Successor available: llama3.3
    · Marked as superseded by newer models
    Replace: ollama pull llama3.3 && ollama rm llama2:7b
```

### Other commands

```bash
omon disk               # disk usage breakdown with bar chart
omon pressure           # memory pressure, swap, model headroom
omon config             # show current config
omon config --init      # create ~/.config/omon/config.toml
omon completions zsh    # print shell completion script
```

## JSON output

Every command supports `--json` for scripting and piping:

```bash
omon list --json | jq '.[].name'
omon bench llama2:7b --json | jq '.avg_gen_tok_s'
omon --json | jq '.memory_pressure.level'
```

## Configuration

```bash
omon config --init      # creates ~/.config/omon/config.toml
```

```toml
[general]
# host = "localhost:11434"
# json = false
# no_pager = false

[watch]
# interval = 2

[serve]
# port = 11435

[cleanup]
# stale_days = 30
```

CLI flags always override config values.

## Shell completions

```bash
# Bash — add to ~/.bashrc
eval "$(omon completions bash)"

# Zsh — add to ~/.zshrc
eval "$(omon completions zsh)"

# Fish
omon completions fish | source
```

Provides tab-completion for commands, flags, model names, task types, and capabilities.

## Command aliases

| Full | Alias |
|---|---|
| `omon list` | `omon ls` |
| `omon show` | `omon info` |
| `omon disk` | `omon du` |
| `omon pressure` | `omon mem` |
| `omon watch` | `omon top` |

## Requirements

- Python 3.10+
- Ollama running locally (or specify `--host`)
- macOS or Linux (macOS with Apple Silicon is the primary target)

## License

MIT
