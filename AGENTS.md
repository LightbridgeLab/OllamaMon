# omon — Project Guidelines

`omon` is a local-first, privacy-focused monitoring and management tool for Ollama. Zero external Python dependencies (stdlib only).

See [PLANNING.md](PLANNING.md) for the full development plan and [ROADMAP.md](ROADMAP.md) for future features.

## Core Constraints

### Zero External Dependencies
This project uses **Python stdlib only**. No exceptions. No `requests`, no `rich`, no `click`, no `flask`. If it's not in `import sys; print(sys.stdlib_module_names)`, it doesn't ship.

Rationale: omon is a small, focused tool. Users should install it and have it work — no dependency conflicts, no supply chain risk, no venv required for `pipx install omon`.

Test dependencies (pytest, etc.) are allowed in `[project.optional-dependencies.dev]` but must never leak into runtime.

### Key stdlib modules in use
- `urllib.request` — HTTP to Ollama API (not `http.client` directly)
- `json` — API responses
- `curses` — TUI
- `http.server` — Web dashboard
- `sqlite3` — Metrics storage
- `argparse` — CLI parsing
- `threading` — Background polling
- `dataclasses` — Data structures
- `pathlib` — File paths
- `re` — Model name parsing
- `tomllib` — Config file parsing (Python 3.11+; degrade gracefully on 3.10)

## Architecture Rules

1. **`api.py` is the only module that makes HTTP calls to Ollama.** All other modules receive and return dataclasses. This makes testing possible without a running Ollama instance.

2. **External API calls (HuggingFace, OpenRouter, etc.) live in `external.py` only.** They are opt-in, cached, and never required for core functionality.

3. **No module imports from a "higher" layer.** The dependency graph flows: `cli → tui/web → bench/decoder/formatter → api/models/store → (stdlib)`. Never backwards.

4. **Every CLI command works independently.** No command requires another to have run first. No hidden init step.

## Coding Conventions

- **Python 3.10+** minimum. Use `match` statements where clearer than if/elif chains. Use `type | None` union syntax.
- **Type hints everywhere** on public function signatures. No `Any` unless genuinely unavoidable.
- **Dataclasses for data, functions for behavior.** Don't make classes with methods when a function taking a dataclass works.
- **No classes wrapping a single method.** If it's just `__init__` + one method, it's a function.
- **ANSI escape codes for terminal color.** No curses for non-TUI output. Keep a simple palette — don't rainbow the terminal.
- **Errors are messages, not stack traces.** If Ollama isn't running, print "Ollama is not running at localhost:11434" and exit 1. Don't dump a ConnectionRefusedError traceback.
- **No global state.** Pass config/state through function arguments.

## Testing

- Tests use `pytest` (dev dependency only).
- Unit tests mock the Ollama API at the `api.py` boundary — pass fake JSON responses, verify dataclass output.
- Integration tests (marked `@pytest.mark.integration`) require a running Ollama instance and are skipped by default.
- The decoder has pure-function tests with known model name inputs and expected outputs.

## File Organization

```
src/omon/           Runtime code (ships to users)
tests/              Tests (dev only)
data/               Static data files (tag dictionary, model mappings)
```

## Commit Style

Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
Subject line under 72 characters. Body explains *why*, not *what*.

## Shell Command Guidelines

Prefer command forms that are simple and matchable to permission patterns:

- **Call venv binaries directly** instead of `source .venv/bin/activate && ...`. Use `.venv/bin/pip`, `.venv/bin/pytest`, etc.
- **Avoid `source`, `eval`, and backtick substitution** when a direct command exists.
- **Prefer single commands over `&&` chains** when possible. Two separate tool calls are better than one chained command that triggers security warnings.
- **Use piped commands sparingly.** If the goal is to read or parse output, consider using Python or a dedicated tool instead.

## What Not To Do

- Don't add a dependency. Solve it with stdlib or don't solve it.
- Don't add abstraction for code that exists in one place. Three copies is better than a premature framework.
- Don't handle errors that can't happen. Trust internal code. Validate at system boundaries (user input, Ollama API responses).
- Don't add features not in PLANNING.md without discussion.
- Don't make the output "clever." Clear and readable beats compact and cryptic.
